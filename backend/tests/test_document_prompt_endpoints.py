"""Unit tests for document and prompt stub API endpoints.

Uses AsyncClient + in-memory overrides via shared FakeSession / api_client
from conftest.py.
"""

from __future__ import annotations

import uuid

import pytest
from shared.models.enums import Role

from tests.conftest import FakeSession, api_client, auth_header
from tests.factories import make_user

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIRM_ID = uuid.uuid4()
_VALID_HASH = "a" * 64  # 64-char hex string (SHA-256)


# ---------------------------------------------------------------------------
# POST /documents/
# ---------------------------------------------------------------------------


class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_stub_returns_201(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/documents/",
                json={
                    "matter_id": str(uuid.uuid4()),
                    "filename": "evidence.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": 1024,
                    "file_hash": _VALID_HASH,
                    "source": "government_production",
                    "classification": "brady",
                },
                headers=auth_header(user),
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "evidence.pdf"
        assert data["source"] == "government_production"
        assert data["classification"] == "brady"
        assert data["file_hash"] == _VALID_HASH
        assert data["firm_id"] == str(user.firm_id)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "field,value",
        [
            ("filename", ""),
            ("content_type", ""),
            ("size_bytes", -1),
            ("file_hash", "tooshort"),
        ],
    )
    async def test_validation_rejects_bad_input(
        self, field: str, value: object
    ) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        payload = {
            "matter_id": str(uuid.uuid4()),
            "filename": "evidence.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
            "file_hash": _VALID_HASH,
        }
        payload[field] = value
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/documents/",
                json=payload,
                headers=auth_header(user),
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /documents/
# ---------------------------------------------------------------------------


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_stub_returns_empty_list(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.get("/documents/", headers=auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /documents/{document_id}
# ---------------------------------------------------------------------------


class TestGetDocument:
    @pytest.mark.asyncio
    async def test_stub_returns_404(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.get(f"/documents/{uuid.uuid4()}", headers=auth_header(user))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /prompts/
# ---------------------------------------------------------------------------


class TestCreatePrompt:
    @pytest.mark.asyncio
    async def test_stub_returns_201_with_canned_response(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/prompts/",
                json={
                    "matter_id": str(uuid.uuid4()),
                    "query": "What Brady material exists?",
                },
                headers=auth_header(user),
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["query"] == "What Brady material exists?"
        assert "stub" in data["response"].lower()
        assert data["firm_id"] == str(user.firm_id)

    @pytest.mark.asyncio
    async def test_validation_rejects_empty_query(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/prompts/",
                json={
                    "matter_id": str(uuid.uuid4()),
                    "query": "",
                },
                headers=auth_header(user),
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /prompts/
# ---------------------------------------------------------------------------


class TestListPrompts:
    @pytest.mark.asyncio
    async def test_stub_returns_empty_list(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.get("/prompts/", headers=auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /prompts/{prompt_id}
# ---------------------------------------------------------------------------


class TestGetPrompt:
    @pytest.mark.asyncio
    async def test_stub_returns_404(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.get(f"/prompts/{uuid.uuid4()}", headers=auth_header(user))
        assert resp.status_code == 404
