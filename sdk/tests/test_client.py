"""Unit tests for opencase.client.OpenCaseClient using httpx.MockTransport."""

from __future__ import annotations

import json
import time

import httpx
import pytest
from shared.models.auth import MfaRequiredResponse, TokenResponse

from opencase.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ServerError,
    ValidationError,
)
from tests.conftest import build_client, make_jwt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_ACCESS = make_jwt(exp=time.time() + 3600)
_VALID_REFRESH = "refresh-token"


def _token_json() -> dict[str, str]:
    return {
        "access_token": _VALID_ACCESS,
        "refresh_token": _VALID_REFRESH,
        "token_type": "bearer",
    }


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------


def test_health() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(
            200, json={"status": "ok", "app": "opencase", "version": "0.1.0"}
        )

    client = build_client(handler)
    result = client.health()
    assert result.status == "ok"
    assert result.app == "opencase"


def test_readiness() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ready"
        return httpx.Response(
            200, json={"status": "ok", "services": {"postgres": "ok"}}
        )

    client = build_client(handler)
    result = client.readiness()
    assert result.status == "ok"
    assert result.services.postgres == "ok"


# ---------------------------------------------------------------------------
# Login — no MFA
# ---------------------------------------------------------------------------


def test_login_success_no_mfa() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_token_json())

    client = build_client(handler)
    result = client.login(email="user@firm.com", password="secret")

    assert isinstance(result, TokenResponse)
    assert client._auth.is_authenticated  # noqa: SLF001


# ---------------------------------------------------------------------------
# Login — MFA required
# ---------------------------------------------------------------------------


def test_login_mfa_required() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path == "/auth/login":
            return httpx.Response(
                200, json={"mfa_required": True, "mfa_token": "mfa-tok"}
            )
        if request.url.path == "/auth/mfa/verify":
            assert body["mfa_token"] == "mfa-tok"
            assert body["totp_code"] == "123456"
            return httpx.Response(200, json=_token_json())
        return httpx.Response(404)

    client = build_client(handler)

    result = client.login(email="user@firm.com", password="secret")
    assert isinstance(result, MfaRequiredResponse)
    assert not client._auth.is_authenticated  # noqa: SLF001

    token_resp = client.verify_mfa(mfa_token="mfa-tok", totp_code="123456")
    assert isinstance(token_resp, TokenResponse)
    assert client._auth.is_authenticated  # noqa: SLF001


# ---------------------------------------------------------------------------
# Login — invalid credentials
# ---------------------------------------------------------------------------


def test_login_invalid_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid credentials"})

    client = build_client(handler)
    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        client.login(email="user@firm.com", password="wrong")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


def test_logout_clears_tokens() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if request.url.path == "/auth/login":
            return httpx.Response(200, json=_token_json())
        if request.url.path == "/auth/logout":
            return httpx.Response(200, json={"detail": "Logged out"})
        return httpx.Response(404)

    client = build_client(handler)
    client.login(email="u@f.com", password="p")
    assert client._auth.is_authenticated  # noqa: SLF001

    result = client.logout()
    assert result.detail == "Logged out"
    assert not client._auth.is_authenticated  # noqa: SLF001


# ---------------------------------------------------------------------------
# Auto-refresh on expired token
# ---------------------------------------------------------------------------


def test_auto_refresh_on_expired_token() -> None:
    """When the access token is expired, the client refreshes before sending."""
    expired_access = make_jwt(exp=time.time() - 60)
    fresh_access = make_jwt(exp=time.time() + 3600)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/auth/refresh":
            return httpx.Response(
                200,
                json={
                    "access_token": fresh_access,
                    "refresh_token": "new-refresh",
                    "token_type": "bearer",
                },
            )
        if request.url.path == "/auth/mfa/setup":
            return httpx.Response(
                200,
                json={
                    "totp_secret": "JBSWY3DPEHPK3PXP",
                    "provisioning_uri": "otpauth://totp/...",
                },
            )
        return httpx.Response(404)

    client = build_client(handler)
    client._auth.store_tokens(expired_access, "old-refresh")  # noqa: SLF001

    result = client.mfa_setup()
    assert result.totp_secret == "JBSWY3DPEHPK3PXP"
    # Refresh was called before the authenticated request
    assert "/auth/refresh" in calls
    assert calls.index("/auth/refresh") < calls.index("/auth/mfa/setup")


# ---------------------------------------------------------------------------
# Auto-refresh on 401 response
# ---------------------------------------------------------------------------


def test_auto_refresh_on_401() -> None:
    """When the server returns 401, the client retries after refreshing."""
    fresh_access = make_jwt(exp=time.time() + 3600)
    attempt = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt
        if request.url.path == "/auth/refresh":
            return httpx.Response(
                200,
                json={
                    "access_token": fresh_access,
                    "refresh_token": "new-refresh",
                    "token_type": "bearer",
                },
            )
        if request.url.path == "/auth/mfa/setup":
            attempt += 1
            if attempt == 1:
                return httpx.Response(401, json={"detail": "Expired"})
            return httpx.Response(
                200,
                json={
                    "totp_secret": "JBSWY3DPEHPK3PXP",
                    "provisioning_uri": "otpauth://totp/...",
                },
            )
        return httpx.Response(404)

    client = build_client(handler)
    valid_access = make_jwt(exp=time.time() + 3600)
    client._auth.store_tokens(valid_access, "old-refresh")  # noqa: SLF001

    result = client.mfa_setup()
    assert result.totp_secret == "JBSWY3DPEHPK3PXP"
    assert attempt == 2  # First 401, then retry succeeds  # noqa: PLR2004


# ---------------------------------------------------------------------------
# Exception mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "exc_type"),
    [
        (401, AuthenticationError),
        (403, AuthorizationError),
        (404, NotFoundError),
        (422, ValidationError),
        (500, ServerError),
        (502, ServerError),
    ],
)
def test_exception_mapping(
    status: int, exc_type: type[Exception]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"detail": "error"})

    client = build_client(handler)
    with pytest.raises(exc_type):
        client.health()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def test_context_manager() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "ok", "app": "opencase", "version": "0.1.0"}
        )

    with build_client(handler) as client:
        result = client.health()
        assert result.status == "ok"


# ---------------------------------------------------------------------------
# MFA management
# ---------------------------------------------------------------------------


def test_mfa_setup() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/mfa/setup":
            return httpx.Response(
                200,
                json={
                    "totp_secret": "JBSWY3DPEHPK3PXP",
                    "provisioning_uri": "otpauth://totp/...",
                },
            )
        return httpx.Response(404)

    client = build_client(handler)
    client._auth.store_tokens(  # noqa: SLF001
        make_jwt(exp=time.time() + 3600), "refresh"
    )
    result = client.mfa_setup()
    assert result.totp_secret == "JBSWY3DPEHPK3PXP"


def test_mfa_confirm() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/mfa/confirm":
            return httpx.Response(200, json={"enabled": True})
        return httpx.Response(404)

    client = build_client(handler)
    client._auth.store_tokens(  # noqa: SLF001
        make_jwt(exp=time.time() + 3600), "refresh"
    )
    result = client.mfa_confirm(totp_code="123456")
    assert result.enabled is True


def test_mfa_disable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/mfa/disable":
            return httpx.Response(200, json={"enabled": False})
        return httpx.Response(404)

    client = build_client(handler)
    client._auth.store_tokens(  # noqa: SLF001
        make_jwt(exp=time.time() + 3600), "refresh"
    )
    result = client.mfa_disable(totp_code="123456")
    assert result.enabled is False
