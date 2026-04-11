"""Unit tests for SDK entity methods (firms, users, matters, matter access).

Uses httpx.MockTransport following the pattern in test_client.py.
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from shared.models.document import DocumentResponse, DuplicateCheckResponse
from shared.models.firm import FirmResponse
from shared.models.matter import MatterResponse, MatterSummary
from shared.models.matter_access import MatterAccessResponse
from shared.models.user import UserResponse, UserSummary

from gideon.exceptions import GideonError
from tests.conftest import build_authenticated_client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIRM_ID = str(uuid.uuid4())
_USER_ID = str(uuid.uuid4())
_MATTER_ID = str(uuid.uuid4())
_NOW = "2025-01-01T00:00:00+00:00"


def _firm_json() -> dict:
    return {"id": _FIRM_ID, "name": "Cora Firm", "created_at": _NOW}


def _user_summary_json(uid: str | None = None) -> dict:
    return {
        "id": uid or _USER_ID,
        "email": "alice@firm.com",
        "first_name": "Alice",
        "last_name": "Smith",
        "role": "attorney",
        "is_active": True,
    }


def _user_response_json(uid: str | None = None) -> dict:
    return {
        **_user_summary_json(uid),
        "title": "Partner",
        "middle_initial": "B",
        "totp_enabled": False,
        "firm_id": _FIRM_ID,
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _matter_summary_json(mid: str | None = None) -> dict:
    return {
        "id": mid or _MATTER_ID,
        "name": "People v. Smith",
        "client_id": str(uuid.uuid4()),
        "status": "open",
        "legal_hold": False,
    }


def _matter_response_json(mid: str | None = None) -> dict:
    return {
        **_matter_summary_json(mid),
        "firm_id": _FIRM_ID,
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _access_json(uid: str | None = None, mid: str | None = None) -> dict:
    return {
        "user_id": uid or _USER_ID,
        "matter_id": mid or _MATTER_ID,
        "view_work_product": False,
        "assigned_at": _NOW,
    }


# ---------------------------------------------------------------------------
# Firms
# ---------------------------------------------------------------------------


def test_get_firm() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/firms/me"
        return httpx.Response(200, json=_firm_json())

    client = build_authenticated_client(handler)
    result = client.get_firm()
    assert isinstance(result, FirmResponse)
    assert result.name == "Cora Firm"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def test_get_current_user() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/me"
        return httpx.Response(200, json=_user_response_json())

    client = build_authenticated_client(handler)
    result = client.get_current_user()
    assert isinstance(result, UserResponse)
    assert result.email == "alice@firm.com"


def test_list_users() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/"
        return httpx.Response(
            200, json=[_user_summary_json(), _user_summary_json(str(uuid.uuid4()))]
        )

    client = build_authenticated_client(handler)
    result = client.list_users()
    assert len(result) == 2  # noqa: PLR2004
    assert all(isinstance(u, UserSummary) for u in result)


def test_get_user() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert f"/users/{_USER_ID}" == request.url.path
        return httpx.Response(200, json=_user_response_json())

    client = build_authenticated_client(handler)
    result = client.get_user(_USER_ID)
    assert isinstance(result, UserResponse)


def test_create_user() -> None:
    sent_body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/"
        assert request.method == "POST"
        sent_body.update(json.loads(request.content))
        return httpx.Response(201, json=_user_response_json())

    client = build_authenticated_client(handler)
    result = client.create_user(
        email="new@firm.com",
        password="a-long-password",
        first_name="New",
        last_name="User",
        role="paralegal",
    )
    assert isinstance(result, UserResponse)
    assert sent_body["email"] == "new@firm.com"
    assert sent_body["role"] == "paralegal"


def test_update_user() -> None:
    sent_body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        sent_body.update(json.loads(request.content))
        return httpx.Response(200, json=_user_response_json())

    client = build_authenticated_client(handler)
    result = client.update_user(_USER_ID, first_name="Updated")
    assert isinstance(result, UserResponse)
    assert sent_body["first_name"] == "Updated"
    # Only provided fields should be sent
    assert "email" not in sent_body


# ---------------------------------------------------------------------------
# Matters
# ---------------------------------------------------------------------------


def test_list_matters() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/matters/"
        return httpx.Response(200, json=[_matter_summary_json()])

    client = build_authenticated_client(handler)
    result = client.list_matters()
    assert len(result) == 1
    assert isinstance(result[0], MatterSummary)


def test_get_matter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert f"/matters/{_MATTER_ID}" == request.url.path
        return httpx.Response(200, json=_matter_response_json())

    client = build_authenticated_client(handler)
    result = client.get_matter(_MATTER_ID)
    assert isinstance(result, MatterResponse)
    assert result.name == "People v. Smith"


def test_create_matter() -> None:
    client_id = str(uuid.uuid4())
    sent_body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        sent_body.update(json.loads(request.content))
        return httpx.Response(201, json=_matter_response_json())

    client = build_authenticated_client(handler)
    result = client.create_matter(name="New Matter", client_id=client_id)
    assert isinstance(result, MatterResponse)
    assert sent_body["name"] == "New Matter"
    assert sent_body["client_id"] == client_id


def test_update_matter() -> None:
    sent_body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        sent_body.update(json.loads(request.content))
        return httpx.Response(200, json=_matter_response_json())

    client = build_authenticated_client(handler)
    result = client.update_matter(_MATTER_ID, status="closed")
    assert isinstance(result, MatterResponse)
    assert sent_body["status"] == "closed"


# ---------------------------------------------------------------------------
# Matter Access
# ---------------------------------------------------------------------------


def test_list_matter_access() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert f"/matters/{_MATTER_ID}/access" == request.url.path
        return httpx.Response(200, json=[_access_json()])

    client = build_authenticated_client(handler)
    result = client.list_matter_access(_MATTER_ID)
    assert len(result) == 1
    assert isinstance(result[0], MatterAccessResponse)


def test_grant_matter_access() -> None:
    sent_body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        sent_body.update(json.loads(request.content))
        return httpx.Response(201, json=_access_json())

    client = build_authenticated_client(handler)
    result = client.grant_matter_access(
        _MATTER_ID, user_id=_USER_ID, view_work_product=False
    )
    assert isinstance(result, MatterAccessResponse)
    assert sent_body["user_id"] == _USER_ID


def test_revoke_matter_access() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert f"/matters/{_MATTER_ID}/access/{_USER_ID}" == request.url.path
        return httpx.Response(200, json={"detail": "Access revoked"})

    client = build_authenticated_client(handler)
    result = client.revoke_matter_access(_MATTER_ID, _USER_ID)
    assert result.detail == "Access revoked"


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

_DOC_ID = str(uuid.uuid4())


def _document_response_json() -> dict:
    return {
        "id": _DOC_ID,
        "firm_id": _FIRM_ID,
        "matter_id": _MATTER_ID,
        "filename": "evidence.pdf",
        "content_type": "application/pdf",
        "size_bytes": 12345,
        "source": "defense",
        "classification": "unclassified",
        "ingestion_status": "pending",
        "legal_hold": False,
        "file_hash": "a" * 64,
        "bates_number": None,
        "uploaded_by": _USER_ID,
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def test_upload_document_multipart(tmp_path) -> None:
    """upload_document sends multipart/form-data with the file."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/documents/"
        assert request.method == "POST"
        ct = request.headers.get("content-type", "")
        captured["content_type"] = ct
        captured["body"] = request.content
        return httpx.Response(201, json=_document_response_json())

    client = build_authenticated_client(handler)
    f = tmp_path / "test.pdf"
    f.write_bytes(b"%PDF-1.4 fake content")

    result = client.upload_document(file_path=f, matter_id=_MATTER_ID)
    assert isinstance(result, DocumentResponse)
    assert result.filename == "evidence.pdf"
    assert "multipart/form-data" in captured["content_type"]
    # File content should be in the body
    assert b"%PDF-1.4 fake content" in captured["body"]


def test_upload_document_409_raises(tmp_path) -> None:
    """upload_document raises GideonError on 409 (duplicate)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={"detail": "A document with the same content already exists"},
        )

    client = build_authenticated_client(handler)
    f = tmp_path / "dup.pdf"
    f.write_bytes(b"duplicate content")

    with pytest.raises(GideonError):
        client.upload_document(file_path=f, matter_id=_MATTER_ID)


def test_check_duplicate_exists() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/documents/check-duplicate"
        assert f"matter_id={_MATTER_ID}" in str(request.url)
        return httpx.Response(200, json={"exists": True, "document_id": _DOC_ID})

    client = build_authenticated_client(handler)
    result = client.check_duplicate(matter_id=_MATTER_ID, file_hash="a" * 64)
    assert isinstance(result, DuplicateCheckResponse)
    assert result.exists is True
    assert str(result.document_id) == _DOC_ID


def test_check_duplicate_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"exists": False, "document_id": None})

    client = build_authenticated_client(handler)
    result = client.check_duplicate(matter_id=_MATTER_ID, file_hash="b" * 64)
    assert result.exists is False
    assert result.document_id is None
