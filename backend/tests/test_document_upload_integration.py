"""Integration tests for the document upload, list, get, and download flow.

These tests run against the full Docker Compose stack (MinIO + PostgreSQL +
FastAPI) and require ``pytest -m integration``.
"""

from __future__ import annotations

import hashlib
from typing import Any

import httpx
import pytest
from minio import Minio  # type: ignore[import-untyped]


def _login(base_url: str, email: str, password: str) -> dict[str, str]:
    """Login and return Authorization header dict."""
    resp = httpx.post(
        f"{base_url}/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    token = data.get("access_token") or data.get("mfa_token")
    return {"Authorization": f"Bearer {token}"}


def _login_user(base_url: str, seed: dict[str, Any], user_key: str) -> dict[str, str]:
    """Login a seeded user by key (e.g. 'user_a')."""
    u = seed[user_key]
    return _login(base_url, u["email"], u["password"])


def _upload_document(
    base_url: str,
    headers: dict[str, str],
    matter_id: str,
    file_content: bytes = b"integration test file content",
    filename: str = "test_doc.pdf",
    content_type: str = "application/pdf",
) -> httpx.Response:
    """Upload a document via multipart form."""
    return httpx.post(
        f"{base_url}/documents/",
        headers=headers,
        files={"file": (filename, file_content, content_type)},
        data={
            "matter_id": matter_id,
            "source": "defense",
            "classification": "unclassified",
        },
        timeout=30,
    )


@pytest.mark.integration
class TestDocumentUploadRoundtrip:
    def test_upload_and_download(self, fastapi_service, seed_demo) -> None:
        """Upload, list, get metadata, download."""
        base_url = fastapi_service
        headers = _login_user(base_url, seed_demo, "user_a")
        matter_id = str(seed_demo["matter_a"]["id"])
        file_content = b"roundtrip integration test content"
        expected_hash = hashlib.sha256(file_content).hexdigest()

        # Upload
        resp = _upload_document(
            base_url,
            headers,
            matter_id,
            file_content=file_content,
        )
        assert resp.status_code == 201, resp.text
        doc = resp.json()
        doc_id = doc["id"]
        assert doc["filename"] == "test_doc.pdf"
        assert doc["size_bytes"] == len(file_content)
        assert doc["file_hash"] == expected_hash
        assert doc["firm_id"] == str(seed_demo["firm_id"])

        # List
        resp = httpx.get(
            f"{base_url}/documents/",
            params={"matter_id": matter_id},
            headers=headers,
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        docs = data["items"]
        assert any(d["id"] == doc_id for d in docs)

        # Get metadata
        resp = httpx.get(
            f"{base_url}/documents/{doc_id}",
            headers=headers,
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json()["file_hash"] == expected_hash

        # Download
        resp = httpx.get(
            f"{base_url}/documents/{doc_id}/download",
            headers=headers,
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.content == file_content

    def test_dedup_rejects_same_hash(self, fastapi_service, seed_demo) -> None:
        """Upload same file twice — second returns 409."""
        base_url = fastapi_service
        headers = _login_user(base_url, seed_demo, "user_a")
        matter_id = str(seed_demo["matter_a"]["id"])
        content = b"dedup test content unique bytes"

        # First upload — success
        resp = _upload_document(
            base_url,
            headers,
            matter_id,
            file_content=content,
            filename="first.pdf",
        )
        assert resp.status_code == 201

        # Second upload (same content) — duplicate
        resp = _upload_document(
            base_url,
            headers,
            matter_id,
            file_content=content,
            filename="second.pdf",
        )
        assert resp.status_code == 409

    def test_same_file_different_matter_accepted(
        self, fastapi_service, seed_demo
    ) -> None:
        """Same file in two matters succeeds."""
        base_url = fastapi_service
        headers = _login_user(base_url, seed_demo, "user_a")
        content = b"cross-matter dedup test"

        # Upload to matter A
        resp = _upload_document(
            base_url,
            headers,
            str(seed_demo["matter_a"]["id"]),
            file_content=content,
        )
        assert resp.status_code == 201

        # Upload to matter B (user A has access to both)
        resp = _upload_document(
            base_url,
            headers,
            str(seed_demo["matter_b"]["id"]),
            file_content=content,
        )
        assert resp.status_code == 201


@pytest.mark.integration
class TestCheckDuplicate:
    def test_check_duplicate_exists(self, fastapi_service, seed_demo) -> None:
        """check-duplicate returns exists=True for a known hash."""
        base_url = fastapi_service
        headers = _login_user(base_url, seed_demo, "user_a")
        matter_id = str(seed_demo["matter_a"]["id"])
        content = b"check-dup integration test content"
        file_hash = hashlib.sha256(content).hexdigest()

        # Upload first
        resp = _upload_document(base_url, headers, matter_id, file_content=content)
        assert resp.status_code == 201
        doc_id = resp.json()["id"]

        # Check duplicate
        resp = httpx.get(
            f"{base_url}/documents/check-duplicate",
            params={"matter_id": matter_id, "file_hash": file_hash},
            headers=headers,
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["exists"] is True
        assert data["document_id"] == doc_id

    def test_check_duplicate_not_found(self, fastapi_service, seed_demo) -> None:
        """check-duplicate returns exists=False for an unknown hash."""
        base_url = fastapi_service
        headers = _login_user(base_url, seed_demo, "user_a")
        matter_id = str(seed_demo["matter_a"]["id"])
        fake_hash = "0" * 64

        resp = httpx.get(
            f"{base_url}/documents/check-duplicate",
            params={"matter_id": matter_id, "file_hash": fake_hash},
            headers=headers,
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["exists"] is False
        assert data["document_id"] is None

    def test_check_duplicate_wrong_matter(self, fastapi_service, seed_demo) -> None:
        """Same hash in a different matter returns exists=False."""
        base_url = fastapi_service
        headers = _login_user(base_url, seed_demo, "user_a")
        content = b"cross-matter dup check content"
        file_hash = hashlib.sha256(content).hexdigest()

        # Upload to matter A
        resp = _upload_document(
            base_url,
            headers,
            str(seed_demo["matter_a"]["id"]),
            file_content=content,
        )
        assert resp.status_code == 201

        # Check in matter B — should not find it
        resp = httpx.get(
            f"{base_url}/documents/check-duplicate",
            params={
                "matter_id": str(seed_demo["matter_b"]["id"]),
                "file_hash": file_hash,
            },
            headers=headers,
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json()["exists"] is False

    def test_check_duplicate_invalid_hash_rejected(
        self, fastapi_service, seed_demo
    ) -> None:
        """Non-hex hash string is rejected with 422."""
        base_url = fastapi_service
        headers = _login_user(base_url, seed_demo, "user_a")
        matter_id = str(seed_demo["matter_a"]["id"])

        resp = httpx.get(
            f"{base_url}/documents/check-duplicate",
            params={"matter_id": matter_id, "file_hash": "Z" * 64},
            headers=headers,
            timeout=10,
        )
        assert resp.status_code == 422

    def test_check_duplicate_no_matter_access(self, fastapi_service, seed_demo) -> None:
        """User without matter access gets 404."""
        base_url = fastapi_service
        headers = _login_user(base_url, seed_demo, "user_b")
        matter_id = str(seed_demo["matter_a"]["id"])

        resp = httpx.get(
            f"{base_url}/documents/check-duplicate",
            params={"matter_id": matter_id, "file_hash": "a" * 64},
            headers=headers,
            timeout=10,
        )
        assert resp.status_code == 404


@pytest.mark.integration
class TestDocumentAccessControl:
    def test_upload_no_matter_access_returns_404(
        self, fastapi_service, seed_demo
    ) -> None:
        """User B (no access to matter A) gets 404."""
        base_url = fastapi_service
        headers = _login_user(base_url, seed_demo, "user_b")
        matter_id = str(seed_demo["matter_a"]["id"])

        resp = _upload_document(base_url, headers, matter_id)
        assert resp.status_code == 404


@pytest.mark.integration
class TestDocumentS3Metadata:
    def test_s3_metadata_stored(
        self, fastapi_service, seed_demo, minio_service
    ) -> None:
        """Verify S3 object metadata fields."""
        base_url = fastapi_service
        headers = _login_user(base_url, seed_demo, "user_a")
        matter_id = str(seed_demo["matter_a"]["id"])
        file_content = b"metadata test unique content"

        resp = _upload_document(
            base_url,
            headers,
            matter_id,
            file_content=file_content,
        )
        assert resp.status_code == 201
        doc = resp.json()

        # Read S3 metadata directly via minio client
        host, port = minio_service
        mc = Minio(
            f"{host}:{port}",
            access_key="gideon",
            secret_key="changeme",  # noqa: S106
            secure=False,
        )

        firm_id = doc["firm_id"]
        doc_id = doc["id"]
        key = f"{firm_id}/{matter_id}/{doc_id}/original.pdf"

        stat = mc.stat_object("gideon", key)
        meta = stat.metadata

        # MinIO lowercases and adds 'x-amz-meta-' prefix
        assert meta.get("x-amz-meta-document-id") == doc_id
        assert meta.get("x-amz-meta-matter-id") == matter_id
        assert meta.get("x-amz-meta-sha256") == doc["file_hash"]
        assert "x-amz-meta-ingestion-timestamp" in meta
