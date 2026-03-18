"""Authentication router — login, logout, refresh, MFA setup/verify/disable."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from opentelemetry import trace
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    MfaConfirmRequest,
    MfaRequiredResponse,
    MfaSetupResponse,
    MfaStatusResponse,
    MfaVerifyRequest,
    RefreshRequest,
    TokenResponse,
)
from app.core.auth import (
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    decode_token,
    encrypt_totp_secret,
    generate_totp_secret,
    get_current_user,
    get_totp_provisioning_uri,
    verify_password,
    verify_totp,
)
from app.core.config import settings
from app.core.metrics import (
    active_sessions,
    login_attempts,
    mfa_challenges,
    token_refresh_attempts,
)
from app.db import get_db
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _store_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """Create a RefreshToken row and return (encoded_jwt, jti)."""
    jti = uuid.uuid4()
    days = settings.auth.refresh_token_expire_days
    expires_at = datetime.now(UTC) + timedelta(days=days)
    row = RefreshToken(id=jti, user_id=user_id, expires_at=expires_at)
    db.add(row)
    token = create_refresh_token(user_id, jti)
    return token, jti


async def _issue_tokens(
    db: AsyncSession,
    user: User,
) -> TokenResponse:
    """Issue an access + refresh token pair."""
    access = create_access_token(user)
    refresh, _ = await _store_refresh_token(db, user.id)
    await db.commit()
    active_sessions.add(1)
    return TokenResponse(access_token=access, refresh_token=refresh)


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=TokenResponse | MfaRequiredResponse,
    responses={401: {}, 423: {}},
)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TokenResponse | MfaRequiredResponse:
    with tracer.start_as_current_span("auth.login"):
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()

        # Generic error — never reveal which field was wrong.
        credentials_exc = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

        if user is None:
            login_attempts.add(1, {"result": "failure"})
            raise credentials_exc

        # Check lockout.
        if user.locked_until and user.locked_until > datetime.now(UTC):
            login_attempts.add(1, {"result": "locked"})
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked",
            )

        if not verify_password(body.password, user.hashed_password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.auth.login_lockout_attempts:
                user.locked_until = datetime.now(UTC) + timedelta(
                    minutes=settings.auth.login_lockout_minutes
                )
                logger.warning("Account locked: user_id=%s", user.id)
            await db.commit()
            login_attempts.add(1, {"result": "failure"})
            raise credentials_exc

        # Password correct — reset failed attempts.
        user.failed_login_attempts = 0
        user.locked_until = None

        if user.totp_enabled:
            await db.commit()
            mfa_token = create_mfa_token(user.id)
            login_attempts.add(1, {"result": "success"})
            return MfaRequiredResponse(mfa_token=mfa_token)

        login_attempts.add(1, {"result": "success"})
        return await _issue_tokens(db, user)


# ---------------------------------------------------------------------------
# POST /auth/mfa/verify
# ---------------------------------------------------------------------------


@router.post("/mfa/verify", response_model=TokenResponse, responses={401: {}})
async def mfa_verify(
    body: MfaVerifyRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TokenResponse:
    with tracer.start_as_current_span("auth.mfa_verify"):
        payload = decode_token(body.mfa_token, expected_type="mfa")
        user_id = payload.get("sub")

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None or not user.totp_enabled or user.totp_secret is None:
            mfa_challenges.add(1, {"result": "failure"})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA state",
            )

        if not verify_totp(user.totp_secret, body.totp_code):
            mfa_challenges.add(1, {"result": "failure"})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code",
            )

        mfa_challenges.add(1, {"result": "success"})
        return await _issue_tokens(db, user)


# ---------------------------------------------------------------------------
# POST /auth/mfa/setup
# ---------------------------------------------------------------------------


@router.post("/mfa/setup", response_model=MfaSetupResponse)
async def mfa_setup(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MfaSetupResponse:
    with tracer.start_as_current_span("auth.mfa_setup"):
        if user.totp_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA already enabled; disable first",
            )

        secret = generate_totp_secret()
        encrypted = encrypt_totp_secret(secret)
        user.totp_secret = encrypted
        await db.commit()

        provisioning_uri = get_totp_provisioning_uri(encrypted, user.email)
        return MfaSetupResponse(totp_secret=secret, provisioning_uri=provisioning_uri)


# ---------------------------------------------------------------------------
# POST /auth/mfa/confirm
# ---------------------------------------------------------------------------


@router.post("/mfa/confirm", response_model=MfaStatusResponse, responses={401: {}})
async def mfa_confirm(
    body: MfaConfirmRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MfaStatusResponse:
    with tracer.start_as_current_span("auth.mfa_confirm"):
        if user.totp_secret is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Run /auth/mfa/setup first",
            )

        if not verify_totp(user.totp_secret, body.totp_code):
            mfa_challenges.add(1, {"result": "failure"})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code",
            )

        user.totp_enabled = True
        user.totp_verified_at = datetime.now(UTC)
        await db.commit()
        mfa_challenges.add(1, {"result": "success"})
        return MfaStatusResponse(enabled=True)


# ---------------------------------------------------------------------------
# POST /auth/mfa/disable
# ---------------------------------------------------------------------------


@router.post("/mfa/disable", response_model=MfaStatusResponse, responses={401: {}})
async def mfa_disable(
    body: MfaConfirmRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MfaStatusResponse:
    with tracer.start_as_current_span("auth.mfa_disable"):
        if not user.totp_enabled or user.totp_secret is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not enabled",
            )

        if not verify_totp(user.totp_secret, body.totp_code):
            mfa_challenges.add(1, {"result": "failure"})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code",
            )

        user.totp_enabled = False
        user.totp_secret = None
        user.totp_verified_at = None
        await db.commit()
        return MfaStatusResponse(enabled=False)


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=TokenResponse, responses={401: {}})
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TokenResponse:
    with tracer.start_as_current_span("auth.token_refresh"):
        payload = decode_token(body.refresh_token, expected_type="refresh")
        jti = payload.get("jti")
        user_id = payload.get("sub")
        token_refresh_attempts.add(1)

        if jti is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        result = await db.execute(select(RefreshToken).where(RefreshToken.id == jti))
        token_row = result.scalar_one_or_none()

        if token_row is None or token_row.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked refresh token",
            )

        if token_row.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired",
            )

        # Revoke the old token (rotation).
        token_row.revoked_at = datetime.now(UTC)

        # Load user for the new access token.
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        return await _issue_tokens(db, user)


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: LogoutRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    with tracer.start_as_current_span("auth.logout"):
        now = datetime.now(UTC)

        if body.refresh_token:
            # Revoke a specific refresh token.
            payload = decode_token(body.refresh_token, expected_type="refresh")
            jti = payload.get("jti")
            if jti:
                await db.execute(
                    update(RefreshToken)
                    .where(RefreshToken.id == jti, RefreshToken.user_id == user.id)
                    .values(revoked_at=now)
                )
        else:
            # Revoke all active refresh tokens for this user.
            await db.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )

        await db.commit()
        active_sessions.add(-1)
        return MessageResponse(detail="Logged out")
