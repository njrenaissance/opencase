"""Unit tests for backend/app/core/auth.py — crypto utilities and dependencies."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pyotp
import pytest
from fastapi import HTTPException

from app.core.auth import (
    _derive_totp_key,
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    decode_token,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_totp_secret,
    get_current_user,
    hash_password,
    verify_password,
    verify_totp,
)
from tests.factories import make_user

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def test_hash_and_verify_password() -> None:
    plain = "correct-horse-battery-staple"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)


def test_verify_password_wrong() -> None:
    hashed = hash_password("right")
    assert not verify_password("wrong", hashed)


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------


def test_create_access_token_claims() -> None:
    user = make_user()
    token = create_access_token(user)
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == str(user.id)
    assert payload["firm_id"] == str(user.firm_id)
    assert payload["role"] == user.role.value
    assert payload["type"] == "access"


def test_create_refresh_token_has_jti() -> None:
    uid = uuid.uuid4()
    jti = uuid.uuid4()
    token = create_refresh_token(uid, jti)
    payload = decode_token(token, expected_type="refresh")
    assert payload["jti"] == str(jti)
    assert payload["sub"] == str(uid)


def test_create_mfa_token_type() -> None:
    uid = uuid.uuid4()
    token = create_mfa_token(uid)
    payload = decode_token(token, expected_type="mfa")
    assert payload["type"] == "mfa"
    assert payload["sub"] == str(uid)


def test_decode_token_wrong_type_raises() -> None:
    user = make_user()
    token = create_access_token(user)
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token, expected_type="refresh")
    assert exc_info.value.status_code == 401


def test_decode_token_expired_raises() -> None:
    from jose import jwt as jose_jwt

    from app.core.config import settings

    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "iat": datetime.now(UTC) - timedelta(hours=2),
        "exp": datetime.now(UTC) - timedelta(hours=1),
    }
    token = jose_jwt.encode(
        payload, settings.auth.secret_key, algorithm=settings.auth.algorithm
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token, expected_type="access")
    assert exc_info.value.status_code == 401


def test_decode_token_garbage_raises() -> None:
    with pytest.raises(HTTPException) as exc_info:
        decode_token("not-a-jwt", expected_type="access")
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# TOTP encryption
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_totp_roundtrip() -> None:
    secret = generate_totp_secret()
    encrypted = encrypt_totp_secret(secret)
    assert encrypted != secret
    assert decrypt_totp_secret(encrypted) == secret


def test_encrypt_totp_unique_nonces() -> None:
    secret = generate_totp_secret()
    a = encrypt_totp_secret(secret)
    b = encrypt_totp_secret(secret)
    assert a != b  # different nonces → different ciphertext


def test_verify_totp_valid() -> None:
    from app.core.auth import _totp_digest

    secret = generate_totp_secret()
    encrypted = encrypt_totp_secret(secret)
    code = pyotp.TOTP(secret, digest=_totp_digest()).now()
    assert verify_totp(encrypted, code)


def test_verify_totp_invalid() -> None:
    secret = generate_totp_secret()
    encrypted = encrypt_totp_secret(secret)
    assert not verify_totp(encrypted, "000000")


def test_derive_totp_key_deterministic() -> None:
    assert _derive_totp_key() == _derive_totp_key()


# ---------------------------------------------------------------------------
# get_current_user dependency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_valid() -> None:
    user = make_user()
    token = create_access_token(user)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await get_current_user(token=token, db=mock_db)
    assert result.id == user.id


@pytest.mark.asyncio
async def test_get_current_user_inactive_raises() -> None:
    user = make_user(is_active=False)
    token = create_access_token(user)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=mock_db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_no_token_raises() -> None:
    mock_db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=None, db=mock_db)
    assert exc_info.value.status_code == 401
