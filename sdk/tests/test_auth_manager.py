"""Unit tests for gideon._auth.AuthManager."""

from __future__ import annotations

import time

import httpx
import pytest

from gideon._auth import AuthManager
from gideon.exceptions import AuthenticationError
from tests.conftest import make_jwt, mock_http

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mgr() -> AuthManager:
    return AuthManager()


# ---------------------------------------------------------------------------
# Token storage
# ---------------------------------------------------------------------------


def test_initial_state(mgr: AuthManager) -> None:
    assert not mgr.is_authenticated
    assert mgr.access_token is None
    assert mgr.refresh_token is None
    assert mgr.authorization_header == {}


def test_store_and_clear(mgr: AuthManager) -> None:
    mgr.store_tokens("access", "refresh")
    assert mgr.is_authenticated
    assert mgr.access_token == "access"
    assert mgr.refresh_token == "refresh"
    assert mgr.authorization_header == {"Authorization": "Bearer access"}

    mgr.clear()
    assert not mgr.is_authenticated
    assert mgr.access_token is None


# ---------------------------------------------------------------------------
# JWT exp peek
# ---------------------------------------------------------------------------


def test_access_token_expired_no_token(mgr: AuthManager) -> None:
    assert mgr.access_token_expired is True


def test_access_token_not_expired(mgr: AuthManager) -> None:
    token = make_jwt(exp=time.time() + 3600)
    mgr.store_tokens(token, "refresh")
    assert mgr.access_token_expired is False


def test_access_token_expired_past(mgr: AuthManager) -> None:
    token = make_jwt(exp=time.time() - 60)
    mgr.store_tokens(token, "refresh")
    assert mgr.access_token_expired is True


def test_access_token_expired_within_buffer(mgr: AuthManager) -> None:
    # Within the 30s buffer — should be considered expired
    token = make_jwt(exp=time.time() + 10)
    mgr.store_tokens(token, "refresh")
    assert mgr.access_token_expired is True


def test_access_token_no_exp_claim(mgr: AuthManager) -> None:
    token = make_jwt(exp=None)
    mgr.store_tokens(token, "refresh")
    assert mgr.access_token_expired is True


def test_peek_exp_malformed_token() -> None:
    assert AuthManager._peek_exp("not-a-jwt") is None  # noqa: SLF001
    assert AuthManager._peek_exp("a.b") is None  # noqa: SLF001
    assert AuthManager._peek_exp("") is None  # noqa: SLF001


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


def test_refresh_success(mgr: AuthManager) -> None:
    new_access = make_jwt(exp=time.time() + 3600)
    new_refresh = "new-refresh"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": new_access,
                "refresh_token": new_refresh,
                "token_type": "bearer",
            },
        )

    mgr.store_tokens("old-access", "old-refresh")
    mgr.refresh(mock_http(handler), "http://test")

    assert mgr.access_token == new_access
    assert mgr.refresh_token == new_refresh


def test_refresh_failure_clears_tokens(mgr: AuthManager) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid"})

    mgr.store_tokens("old-access", "old-refresh")

    with pytest.raises(AuthenticationError):
        mgr.refresh(mock_http(handler), "http://test")

    assert not mgr.is_authenticated


def test_refresh_no_token_raises(mgr: AuthManager) -> None:
    with pytest.raises(AuthenticationError, match="No refresh token"):
        mgr.refresh(mock_http(lambda _: httpx.Response(200)), "http://test")
