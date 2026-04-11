"""Shared test helpers for the SDK test suite."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable

import httpx

from gideon import Client

Handler = Callable[[httpx.Request], httpx.Response]


def make_jwt(exp: float | None = None, extra: dict[str, object] | None = None) -> str:
    """Build a fake JWT with the given exp claim (no real signature)."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).rstrip(
        b"="
    )
    payload: dict[str, object] = {"sub": "user-id"}
    if exp is not None:
        payload["exp"] = exp
    if extra:
        payload.update(extra)
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    sig = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=")
    return f"{header.decode()}.{body.decode()}.{sig.decode()}"


def mock_http(handler: Handler) -> httpx.Client:
    """Create an httpx.Client backed by a mock transport."""
    return httpx.Client(transport=httpx.MockTransport(handler))


def build_client(handler: Handler) -> Client:
    """Create a Client backed by a mock transport."""
    client = Client(base_url="http://test")
    client._http = mock_http(handler)  # noqa: SLF001
    return client


def build_authenticated_client(handler: Handler) -> Client:
    """Create a Client with pre-stored auth tokens."""
    client = build_client(handler)
    token = make_jwt(exp=time.time() + 3600)
    client._auth.store_tokens(token, "refresh")  # noqa: SLF001
    return client
