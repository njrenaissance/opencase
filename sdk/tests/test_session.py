"""Unit tests for opencase.session.Session context manager."""

from __future__ import annotations

import json
import time

import httpx
import pytest

from opencase import Client, Session
from opencase.exceptions import AuthenticationError
from tests.conftest import make_jwt

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


def _build_session(handler: httpx.MockTransport | None = None) -> Session:
    """Create a Session with a mock HTTP transport."""
    session = Session(
        "http://test",
        email="user@firm.com",
        password="secret",
    )
    if handler is not None:
        session._client._http = httpx.Client(transport=handler)  # noqa: SLF001
    return session


# ---------------------------------------------------------------------------
# Login lifecycle
# ---------------------------------------------------------------------------


def test_enter_calls_login_and_returns_client() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            body = json.loads(request.content)
            assert body["email"] == "user@firm.com"
            assert body["password"] == "secret"
            return httpx.Response(200, json=_token_json())
        return httpx.Response(404)

    session = _build_session(httpx.MockTransport(handler))
    client = session.__enter__()

    assert isinstance(client, Client)
    assert client._auth.is_authenticated  # noqa: SLF001


def test_credentials_cleared_after_enter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_token_json())

    session = _build_session(httpx.MockTransport(handler))
    session.__enter__()

    assert session._email is None  # noqa: SLF001
    assert session._password is None  # noqa: SLF001


# ---------------------------------------------------------------------------
# Logout lifecycle
# ---------------------------------------------------------------------------


def test_exit_calls_logout_and_close() -> None:
    logout_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal logout_called
        if request.url.path == "/auth/login":
            return httpx.Response(200, json=_token_json())
        if request.url.path == "/auth/logout":
            logout_called = True
            return httpx.Response(200, json={"detail": "Logged out"})
        return httpx.Response(404)

    with _build_session(httpx.MockTransport(handler)) as client:
        assert client._auth.is_authenticated  # noqa: SLF001

    assert logout_called


def test_exit_calls_logout_on_exception() -> None:
    logout_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal logout_called
        if request.url.path == "/auth/login":
            return httpx.Response(200, json=_token_json())
        if request.url.path == "/auth/logout":
            logout_called = True
            return httpx.Response(200, json={"detail": "Logged out"})
        return httpx.Response(404)

    session = _build_session(httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="boom"), session:
        raise RuntimeError("boom")

    assert logout_called


def test_exception_propagated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json=_token_json())
        if request.url.path == "/auth/logout":
            return httpx.Response(200, json={"detail": "Logged out"})
        return httpx.Response(404)

    session = _build_session(httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="test error"), session:
        raise ValueError("test error")


# ---------------------------------------------------------------------------
# MFA required
# ---------------------------------------------------------------------------


def test_mfa_required_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(
                200, json={"mfa_required": True, "mfa_token": "mfa-tok"}
            )
        return httpx.Response(404)

    session = _build_session(httpx.MockTransport(handler))
    with pytest.raises(AuthenticationError, match="MFA required"):
        session.__enter__()


# ---------------------------------------------------------------------------
# Login failure
# ---------------------------------------------------------------------------


def test_login_failure_closes_client() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid credentials"})

    session = _build_session(httpx.MockTransport(handler))
    with pytest.raises(AuthenticationError), session:
        pass  # pragma: no cover


def test_credentials_cleared_on_login_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid credentials"})

    session = _build_session(httpx.MockTransport(handler))
    with pytest.raises(AuthenticationError):
        session.__enter__()

    assert session._email is None  # noqa: SLF001
    assert session._password is None  # noqa: SLF001


# ---------------------------------------------------------------------------
# Async not implemented
# ---------------------------------------------------------------------------


def test_async_aenter_not_implemented() -> None:
    import asyncio

    session = Session("http://test", email="u@f.com", password="p")
    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(NotImplementedError, match="Async not supported"):
            loop.run_until_complete(session.__aenter__())
    finally:
        loop.close()


def test_async_aexit_not_implemented() -> None:
    import asyncio

    session = Session("http://test", email="u@f.com", password="p")
    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(NotImplementedError, match="Async not supported"):
            loop.run_until_complete(session.__aexit__(None, None, None))
    finally:
        loop.close()
