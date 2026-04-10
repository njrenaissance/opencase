"""Unit tests for document and prompt API endpoints.

Uses AsyncClient + in-memory overrides via shared FakeSession / api_client
from conftest.py.  Document tests use multipart form uploads with a mocked
S3StorageService.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from shared.models.enums import Role

from app.storage import get_storage_service
from tests.conftest import FakeSession, api_client, auth_header, fake_with_docs
from tests.factories import make_document, make_user

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIRM_ID = uuid.uuid4()
_MATTER_ID = uuid.uuid4()

_FILE_CONTENT = b"hello world test document content"
_FILE_NAME = "evidence.pdf"
_FILE_CT = "application/pdf"


def _mock_storage() -> MagicMock:
    """Return a mock S3StorageService that records upload calls."""
    mock = MagicMock()
    mock.upload_document = AsyncMock(return_value="fake/key/original.pdf")
    mock.download_document = AsyncMock(return_value=(_FILE_CONTENT, _FILE_CT))
    mock.delete_document = AsyncMock()
    return mock


def _upload_kwargs(
    matter_id: uuid.UUID | None = None,
    source: str = "defense",
    classification: str = "unclassified",
    bates_number: str | None = None,
) -> dict:
    """Build multipart form data + files for a document upload."""
    data: dict[str, str] = {
        "matter_id": str(matter_id or _MATTER_ID),
        "source": source,
        "classification": classification,
    }
    if bates_number is not None:
        data["bates_number"] = bates_number
    return {
        "files": {"file": (_FILE_NAME, _FILE_CONTENT, _FILE_CT)},
        "data": data,
    }


# ---------------------------------------------------------------------------
# POST /documents/
# ---------------------------------------------------------------------------


class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_upload_returns_201(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        mock_storage = _mock_storage()

        from app.main import app

        app.dependency_overrides[get_storage_service] = lambda: mock_storage
        try:
            async with api_client(user, fake) as ac:
                kw = _upload_kwargs(
                    source="government_production",
                    classification="brady",
                )
                resp = await ac.post(
                    "/documents/",
                    headers=auth_header(user),
                    **kw,
                )
        finally:
            app.dependency_overrides.pop(get_storage_service, None)

        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == _FILE_NAME
        assert data["source"] == "government_production"
        assert data["classification"] == "brady"
        assert len(data["file_hash"]) == 64
        assert data["firm_id"] == str(user.firm_id)
        assert data["size_bytes"] == len(_FILE_CONTENT)
        mock_storage.upload_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_missing_file_returns_422(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        mock_storage = _mock_storage()

        from app.main import app

        app.dependency_overrides[get_storage_service] = lambda: mock_storage
        try:
            async with api_client(user, fake) as ac:
                resp = await ac.post(
                    "/documents/",
                    data={"matter_id": str(_MATTER_ID)},
                    headers=auth_header(user),
                )
        finally:
            app.dependency_overrides.pop(get_storage_service, None)

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_missing_matter_id_returns_422(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        mock_storage = _mock_storage()

        from app.main import app

        app.dependency_overrides[get_storage_service] = lambda: mock_storage
        try:
            async with api_client(user, fake) as ac:
                resp = await ac.post(
                    "/documents/",
                    files={"file": (_FILE_NAME, _FILE_CONTENT, _FILE_CT)},
                    headers=auth_header(user),
                )
        finally:
            app.dependency_overrides.pop(get_storage_service, None)

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /documents/
# ---------------------------------------------------------------------------


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_documents(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = fake_with_docs([])
        async with api_client(user, fake) as ac:
            resp = await ac.get("/documents/", headers=auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_documents_for_admin(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        doc = make_document(firm_id=_FIRM_ID, matter_id=_MATTER_ID, uploaded_by=user.id)
        fake = fake_with_docs([doc])
        async with api_client(user, fake) as ac:
            resp = await ac.get("/documents/", headers=auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(doc.id)
        assert data["total"] == 1
        assert data["offset"] == 0
        assert data["limit"] == 50


# ---------------------------------------------------------------------------
# GET /documents/{document_id}
# ---------------------------------------------------------------------------


class TestGetDocument:
    @pytest.mark.asyncio
    async def test_returns_404_when_not_found(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.get(f"/documents/{uuid.uuid4()}", headers=auth_header(user))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_document_metadata(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        doc = make_document(firm_id=_FIRM_ID, matter_id=_MATTER_ID, uploaded_by=user.id)
        fake = FakeSession()
        fake.add_result(doc)
        async with api_client(user, fake) as ac:
            resp = await ac.get(f"/documents/{doc.id}", headers=auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(doc.id)
        assert data["filename"] == doc.filename
        assert data["file_hash"] == doc.file_hash


# ---------------------------------------------------------------------------
# GET /documents/{document_id}/download
# ---------------------------------------------------------------------------


class TestDownloadDocument:
    @pytest.mark.asyncio
    async def test_returns_file_bytes(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        doc = make_document(firm_id=_FIRM_ID, matter_id=_MATTER_ID, uploaded_by=user.id)
        fake = FakeSession()
        fake.add_result(doc)
        mock_storage = _mock_storage()

        from app.main import app

        app.dependency_overrides[get_storage_service] = lambda: mock_storage
        try:
            async with api_client(user, fake) as ac:
                resp = await ac.get(
                    f"/documents/{doc.id}/download", headers=auth_header(user)
                )
        finally:
            app.dependency_overrides.pop(get_storage_service, None)

        assert resp.status_code == 200
        assert resp.content == _FILE_CONTENT
        assert "attachment" in resp.headers.get("content-disposition", "")
        mock_storage.download_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_404_when_not_found(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        mock_storage = _mock_storage()

        from app.main import app

        app.dependency_overrides[get_storage_service] = lambda: mock_storage
        try:
            async with api_client(user, fake) as ac:
                resp = await ac.get(
                    f"/documents/{uuid.uuid4()}/download", headers=auth_header(user)
                )
        finally:
            app.dependency_overrides.pop(get_storage_service, None)

        assert resp.status_code == 404


# Chat endpoint tests have been moved to test_chats.py
