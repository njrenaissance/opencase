"""Unit tests for the /chats API endpoints.

Uses AsyncClient + in-memory overrides via FakeSession / api_client from conftest.py.
The RAG pipeline is mocked at the import boundary so no running services are needed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from shared.models.enums import Role

from tests.conftest import FakeSession, api_client, auth_header
from tests.factories import make_user

_FIRM_ID = uuid.uuid4()
_MATTER_ID = uuid.uuid4()
_SESSION_ID = uuid.uuid4()
_QUERY_ID = uuid.uuid4()


def _make_fake_session_obj() -> MagicMock:
    s = MagicMock()
    s.id = _SESSION_ID
    s.firm_id = _FIRM_ID
    s.matter_id = _MATTER_ID
    return s


def _make_fake_query_obj(response: str = "The answer is 42.") -> MagicMock:
    q = MagicMock()
    q.id = _QUERY_ID
    q.session_id = _SESSION_ID
    q.query = "What Brady material exists?"
    q.response = response
    q.model_name = "tinyllama"
    q.created_at = datetime.now(UTC)
    return q


# ---------------------------------------------------------------------------
# POST /chats/
# ---------------------------------------------------------------------------


class TestSubmitQuery:
    @pytest.mark.asyncio
    async def test_returns_201_with_real_response(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        fake_session = _make_fake_session_obj()
        fake_query = _make_fake_query_obj()

        with patch(
            "app.api.chats.run_query",
            AsyncMock(return_value=(fake_session, fake_query)),
        ):
            async with api_client(user, fake) as ac:
                resp = await ac.post(
                    "/chats/",
                    json={
                        "matter_id": str(_MATTER_ID),
                        "query": "What Brady material exists?",
                    },
                    headers=auth_header(user),
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["query"] == "What Brady material exists?"
        assert data["matter_id"] == str(_MATTER_ID)
        assert data["response"] == "The answer is 42."
        assert data["session_id"] == str(_SESSION_ID)
        assert data["id"] == str(_QUERY_ID)
        # No longer a stub response
        assert "stub" not in data["response"].lower()

    @pytest.mark.asyncio
    async def test_with_explicit_session_id(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        fake_session = _make_fake_session_obj()
        fake_query = _make_fake_query_obj()

        with patch(
            "app.api.chats.run_query",
            AsyncMock(return_value=(fake_session, fake_query)),
        ):
            async with api_client(user, fake) as ac:
                resp = await ac.post(
                    "/chats/",
                    json={
                        "matter_id": str(_MATTER_ID),
                        "session_id": str(_SESSION_ID),
                        "query": "Who are the witnesses?",
                    },
                    headers=auth_header(user),
                )

        assert resp.status_code == 201
        assert resp.json()["session_id"] == str(_SESSION_ID)

    @pytest.mark.asyncio
    async def test_matter_access_denied_returns_404(self) -> None:
        """build_permission_filter raises 404 when user has no matter access."""
        user = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        fake = FakeSession()

        with patch(
            "app.api.chats.run_query",
            AsyncMock(side_effect=HTTPException(status_code=status.HTTP_404_NOT_FOUND)),
        ):
            async with api_client(user, fake) as ac:
                resp = await ac.post(
                    "/chats/",
                    json={
                        "matter_id": str(_MATTER_ID),
                        "query": "What Brady material exists?",
                    },
                    headers=auth_header(user),
                )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_requires_authentication(self) -> None:
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/chats/",
                json={
                    "matter_id": str(_MATTER_ID),
                    "query": "Test query",
                },
            )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_validation_rejects_empty_query(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/chats/",
                json={
                    "matter_id": str(_MATTER_ID),
                    "query": "",
                },
                headers=auth_header(user),
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_validation_rejects_missing_matter_id(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/chats/",
                json={"query": "Missing matter_id"},
                headers=auth_header(user),
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_validation_rejects_missing_query(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/chats/",
                json={"matter_id": str(_MATTER_ID)},
                headers=auth_header(user),
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /chats/stream
# ---------------------------------------------------------------------------


class TestSubmitQueryStream:
    @pytest.mark.asyncio
    async def test_returns_sse_content_type(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()

        async def _fake_stream(*_a: object, **_kw: object):  # type: ignore[return]
            yield "Hello"
            yield " world"

        with patch("app.api.chats.stream_query", _fake_stream):
            async with api_client(user, fake) as ac:
                resp = await ac.post(
                    "/chats/stream",
                    json={
                        "matter_id": str(_MATTER_ID),
                        "query": "What Brady material exists?",
                    },
                    headers=auth_header(user),
                )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    @pytest.mark.asyncio
    async def test_response_body_contains_sse_data_lines(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()

        async def _fake_stream(*_a: object, **_kw: object):  # type: ignore[return]
            yield "Hello"
            yield " world"

        with patch("app.api.chats.stream_query", _fake_stream):
            async with api_client(user, fake) as ac:
                resp = await ac.post(
                    "/chats/stream",
                    json={
                        "matter_id": str(_MATTER_ID),
                        "query": "What Brady material exists?",
                    },
                    headers=auth_header(user),
                )

        body = resp.text
        assert "data:" in body
        assert "[DONE]" in body

    @pytest.mark.asyncio
    async def test_requires_authentication(self) -> None:
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/chats/stream",
                json={
                    "matter_id": str(_MATTER_ID),
                    "query": "Test query",
                },
            )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_error_mid_stream_yields_error_frame_then_done(self) -> None:
        """Exceptions raised inside stream_query produce an SSE error frame."""
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()

        async def _failing_stream(*_a: object, **_kw: object):  # type: ignore[return]
            yield "partial"
            raise RuntimeError("Ollama disconnected")

        with patch("app.api.chats.stream_query", _failing_stream):
            async with api_client(user, fake) as ac:
                resp = await ac.post(
                    "/chats/stream",
                    json={
                        "matter_id": str(_MATTER_ID),
                        "query": "What Brady material exists?",
                    },
                    headers=auth_header(user),
                )

        assert resp.status_code == 200
        body = resp.text
        assert "Ollama disconnected" in body
        assert "[DONE]" in body

    @pytest.mark.asyncio
    async def test_validation_rejects_empty_query(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/chats/stream",
                json={
                    "matter_id": str(_MATTER_ID),
                    "query": "",
                },
                headers=auth_header(user),
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /chats/sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    @pytest.mark.asyncio
    async def test_stub_returns_empty_list(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.get("/chats/sessions", headers=auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_requires_authentication(self) -> None:
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/chats/sessions")
        assert resp.status_code == 401
