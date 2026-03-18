"""Unit tests for auth API endpoints using AsyncClient + in-memory overrides."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pyotp
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import (
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    encrypt_totp_secret,
    generate_totp_secret,
    hash_password,
)
from app.db import get_db
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import Role, User
from app.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIRM_ID = uuid.uuid4()
_PASSWORD = "test-password-123"  # noqa: S105 — test-only


def _make_user(**overrides: object) -> User:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "firm_id": _FIRM_ID,
        "email": "attorney@corafirm.com",
        "hashed_password": hash_password(_PASSWORD),
        "first_name": "Virginia",
        "last_name": "Cora",
        "role": Role.attorney,
        "is_active": True,
        "totp_enabled": False,
        "totp_secret": None,
        "totp_verified_at": None,
        "failed_login_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return User(**defaults)


class FakeSession:
    """Minimal async session stand-in that tracks added objects and commits."""

    def __init__(self, query_results: dict[type, object] | None = None) -> None:
        self._added: list[object] = []
        self._query_results = query_results or {}
        self.committed = False

    async def execute(self, stmt: object) -> MagicMock:
        # Inspect the statement to determine the target model.
        result = MagicMock()
        # Return the pre-configured result for any query.
        for _model_cls, obj in self._query_results.items():
            result.scalar_one_or_none.return_value = obj
            return result
        result.scalar_one_or_none.return_value = None
        return result

    def add(self, obj: object) -> None:
        self._added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


def _override_db(user: User | None = None, refresh_token: RefreshToken | None = None):
    """Create a get_db override that returns a FakeSession."""
    results: dict[type, object] = {}
    if user is not None:
        results[User] = user
    if refresh_token is not None:
        results[RefreshToken] = refresh_token

    fake = FakeSession(query_results=results)

    async def _get_db() -> AsyncGenerator[FakeSession, None]:
        yield fake

    return _get_db, fake


@pytest.fixture
def user_no_mfa() -> User:
    return _make_user()


@pytest.fixture
def user_with_mfa() -> User:
    secret = generate_totp_secret()
    encrypted = encrypt_totp_secret(secret)
    return _make_user(
        totp_enabled=True,
        totp_secret=encrypted,
        totp_verified_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success_no_mfa(user_no_mfa: User) -> None:
    override, _ = _override_db(user=user_no_mfa)
    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/auth/login",
                json={"email": user_no_mfa.email, "password": _PASSWORD},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"  # noqa: S105
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_success_mfa_enabled(user_with_mfa: User) -> None:
    override, _ = _override_db(user=user_with_mfa)
    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/auth/login",
                json={"email": user_with_mfa.email, "password": _PASSWORD},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mfa_required"] is True
        assert "mfa_token" in data
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_invalid_password(user_no_mfa: User) -> None:
    override, _ = _override_db(user=user_no_mfa)
    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/auth/login",
                json={"email": user_no_mfa.email, "password": "wrong"},
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_locked_account(user_no_mfa: User) -> None:
    user_no_mfa.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    override, _ = _override_db(user=user_no_mfa)
    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/auth/login",
                json={"email": user_no_mfa.email, "password": _PASSWORD},
            )
        assert resp.status_code == 423
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_nonexistent_user() -> None:
    override, _ = _override_db()  # no user in DB
    app.dependency_overrides[get_db] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/auth/login",
                json={"email": "nobody@example.com", "password": "anything"},
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# MFA verify tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mfa_verify_valid(user_with_mfa: User) -> None:
    override, _ = _override_db(user=user_with_mfa)
    app.dependency_overrides[get_db] = override
    try:
        mfa_token = create_mfa_token(user_with_mfa.id)
        secret = decrypt_totp_for_test(user_with_mfa.totp_secret)
        code = pyotp.TOTP(secret).now()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/auth/mfa/verify",
                json={"mfa_token": mfa_token, "totp_code": code},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_mfa_verify_invalid_code(user_with_mfa: User) -> None:
    override, _ = _override_db(user=user_with_mfa)
    app.dependency_overrides[get_db] = override
    try:
        mfa_token = create_mfa_token(user_with_mfa.id)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/auth/mfa/verify",
                json={"mfa_token": mfa_token, "totp_code": "000000"},
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Refresh tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_valid(user_no_mfa: User) -> None:
    jti = uuid.uuid4()
    token_row = RefreshToken(
        id=jti,
        user_id=user_no_mfa.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        revoked_at=None,
    )

    # The FakeSession needs to return different objects for different queries.
    # For simplicity, patch the execute to return the right object per call.
    call_count = 0

    async def _execute(stmt: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalar_one_or_none.return_value = token_row
        else:
            result.scalar_one_or_none.return_value = user_no_mfa
        return result

    fake = FakeSession()
    fake.execute = _execute  # type: ignore[assignment]

    async def _get_db() -> AsyncGenerator[FakeSession, None]:
        yield fake

    app.dependency_overrides[get_db] = _get_db
    try:
        refresh_jwt = create_refresh_token(user_no_mfa.id, jti)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/auth/refresh", json={"refresh_token": refresh_jwt})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_refresh_revoked_rejected(user_no_mfa: User) -> None:
    jti = uuid.uuid4()
    token_row = RefreshToken(
        id=jti,
        user_id=user_no_mfa.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        revoked_at=datetime.now(UTC),  # revoked
    )

    override, _ = _override_db(refresh_token=token_row)
    app.dependency_overrides[get_db] = override
    try:
        refresh_jwt = create_refresh_token(user_no_mfa.id, jti)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/auth/refresh", json={"refresh_token": refresh_jwt})
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Logout tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout(user_no_mfa: User) -> None:
    override, fake = _override_db(user=user_no_mfa)
    app.dependency_overrides[get_db] = override

    # Patch execute to handle both the get_current_user SELECT and the UPDATE.
    original_execute = fake.execute

    async def _patched_execute(stmt: object) -> MagicMock:
        # UPDATE statements don't need a return value with scalar_one_or_none.
        result = await original_execute(stmt)
        return result

    fake.execute = _patched_execute  # type: ignore[assignment]

    try:
        access = create_access_token(user_no_mfa)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/auth/logout",
                json={},
                headers={"Authorization": f"Bearer {access}"},
            )
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Logged out"
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def decrypt_totp_for_test(encrypted: str | None) -> str:
    """Decrypt a TOTP secret — test helper."""
    from app.core.auth import decrypt_totp_secret

    assert encrypted is not None
    return decrypt_totp_secret(encrypted)
