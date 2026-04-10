"""Unit tests for the /chats API endpoints.

Uses AsyncClient + in-memory overrides via FakeSession / api_client from conftest.py.
The RAG pipeline is not yet wired — endpoints return stub responses.
"""

from __future__ import annotations

import uuid

import pytest
from shared.models.enums import Role

from tests.conftest import FakeSession, api_client, auth_header
from tests.factories import make_user

_FIRM_ID = uuid.uuid4()
_MATTER_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# POST /chats/
# ---------------------------------------------------------------------------


class TestSubmitQuery:
    @pytest.mark.asyncio
    async def test_stub_returns_201_with_canned_response(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
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
        assert "stub" in data["response"].lower()
        assert "session_id" in data
        assert "id" in data

    @pytest.mark.asyncio
    async def test_with_explicit_session_id(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        session_id = uuid.uuid4()
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/chats/",
                json={
                    "matter_id": str(_MATTER_ID),
                    "session_id": str(session_id),
                    "query": "Who are the witnesses?",
                },
                headers=auth_header(user),
            )
        assert resp.status_code == 201
        assert resp.json()["session_id"] == str(session_id)

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
