"""Authentication utilities — JWT, bcrypt, TOTP, FastAPI dependencies."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import pyotp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db
from app.db.models.user import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=settings.auth.bcrypt_rounds)
    return bcrypt.hashpw(plain.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# TOTP encryption (AES-256-GCM with HKDF-derived key)
# ---------------------------------------------------------------------------

_TOTP_HKDF_INFO = b"totp-encryption"
_NONCE_BYTES = 12  # AES-GCM standard nonce length


def _derive_totp_key() -> bytes:
    """Derive a 32-byte AES key from auth.secret_key via HKDF."""
    hkdf = HKDF(
        algorithm=SHA256(),
        length=32,
        salt=None,
        info=_TOTP_HKDF_INFO,
    )
    return hkdf.derive(settings.auth.secret_key.encode())


# Cache the derived key for the lifetime of the process.
_totp_key: bytes | None = None


def _get_totp_key() -> bytes:
    global _totp_key  # noqa: PLW0603
    if _totp_key is None:
        _totp_key = _derive_totp_key()
    return _totp_key


def encrypt_totp_secret(plaintext: str) -> str:
    """Encrypt a TOTP secret with AES-256-GCM.

    Returns base64(nonce || ciphertext || tag).
    """
    key = _get_totp_key()
    nonce = os.urandom(_NONCE_BYTES)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt_totp_secret(ciphertext_b64: str) -> str:
    """Decrypt a TOTP secret previously encrypted with encrypt_totp_secret."""
    key = _get_totp_key()
    raw = base64.b64decode(ciphertext_b64)
    nonce = raw[:_NONCE_BYTES]
    ct = raw[_NONCE_BYTES:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode()


_DIGEST_MAP = {"sha1": hashlib.sha1, "sha256": hashlib.sha256, "sha512": hashlib.sha512}


def _totp_digest() -> Callable[..., Any]:
    """Return the hash constructor for the configured TOTP digest."""
    return _DIGEST_MAP[settings.auth.totp_digest]


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(encrypted_secret: str, code: str) -> bool:
    """Decrypt the stored secret and verify the TOTP code."""
    secret = decrypt_totp_secret(encrypted_secret)
    totp = pyotp.TOTP(secret, digest=_totp_digest())
    return totp.verify(code, valid_window=settings.auth.totp_window)


def get_totp_provisioning_uri(encrypted_secret: str, email: str) -> str:
    secret = decrypt_totp_secret(encrypted_secret)
    totp = pyotp.TOTP(secret, digest=_totp_digest())
    return totp.provisioning_uri(name=email, issuer_name=settings.auth.totp_issuer)


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

_MFA_TOKEN_MINUTES = 5


def _create_token(
    data: dict[str, Any],
    token_type: str,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(UTC)
    payload = {
        **data,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    key = settings.auth.secret_key
    alg = settings.auth.algorithm
    encoded: str = jwt.encode(payload, key, algorithm=alg)
    return encoded


def create_access_token(user: User) -> str:
    return _create_token(
        data={
            "sub": str(user.id),
            "firm_id": str(user.firm_id),
            "role": user.role.value,
        },
        token_type="access",  # noqa: S106 — not a password
        expires_delta=timedelta(minutes=settings.auth.access_token_expire_minutes),
    )


def create_refresh_token(user_id: uuid.UUID, jti: uuid.UUID) -> str:
    return _create_token(
        data={"sub": str(user_id), "jti": str(jti)},
        token_type="refresh",  # noqa: S106 — not a password
        expires_delta=timedelta(days=settings.auth.refresh_token_expire_days),
    )


def create_mfa_token(user_id: uuid.UUID) -> str:
    return _create_token(
        data={"sub": str(user_id)},
        token_type="mfa",  # noqa: S106 — not a password
        expires_delta=timedelta(minutes=_MFA_TOKEN_MINUTES),
    )


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """Decode a JWT and verify the ``type`` claim matches *expected_type*.

    Raises ``HTTPException(401)`` on any failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.auth.secret_key,
            algorithms=[settings.auth.algorithm],
        )
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        raise credentials_exception from exc

    if payload.get("type") != expected_type:
        logger.debug(
            "Token type mismatch: expected=%s got=%s",
            expected_type,
            payload.get("type"),
        )
        raise credentials_exception

    return payload


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> User:
    """Decode the access token and return the active User."""
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token, expected_type="access")
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
