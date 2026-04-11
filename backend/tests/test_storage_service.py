"""Unit tests for app.storage.s3 — S3StorageService with mocked Minio client."""

from __future__ import annotations

import uuid
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.storage.s3 import S3StorageService


@pytest.fixture
def s3_settings() -> MagicMock:
    settings = MagicMock()
    settings.endpoint = "minio:9000"
    settings.access_key = "testkey"
    settings.secret_key = "testsecret"  # noqa: S105
    settings.use_ssl = False
    settings.region = "us-east-1"
    settings.bucket = "gideon"
    return settings


@pytest.fixture
def mock_minio() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(s3_settings: MagicMock, mock_minio: MagicMock) -> S3StorageService:
    with patch("app.storage.s3.Minio", return_value=mock_minio):
        svc = S3StorageService(s3_settings)
    return svc


class TestObjectKey:
    def test_key_pattern(self) -> None:
        firm = uuid.uuid4()
        matter = uuid.uuid4()
        doc = uuid.uuid4()
        key = S3StorageService.object_key(firm, matter, doc, "pdf")
        assert key == f"{firm}/{matter}/{doc}/original.pdf"

    def test_key_with_different_extension(self) -> None:
        firm = uuid.uuid4()
        matter = uuid.uuid4()
        doc = uuid.uuid4()
        key = S3StorageService.object_key(firm, matter, doc, "docx")
        assert key.endswith("/original.docx")


class TestUploadDocument:
    @pytest.mark.asyncio
    async def test_calls_put_object_with_correct_args(
        self, service: S3StorageService, mock_minio: MagicMock
    ) -> None:
        firm_id = uuid.uuid4()
        matter_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        data = BytesIO(b"file content")
        file_hash = "a" * 64

        key = await service.upload_document(
            firm_id=firm_id,
            matter_id=matter_id,
            document_id=doc_id,
            extension="pdf",
            data=data,
            size=12,
            content_type="application/pdf",
            file_hash=file_hash,
        )

        expected_key = f"{firm_id}/{matter_id}/{doc_id}/original.pdf"
        assert key == expected_key

        mock_minio.put_object.assert_called_once()
        call_args = mock_minio.put_object.call_args
        assert call_args[0][0] == "gideon"  # bucket
        assert call_args[0][1] == expected_key  # key

    @pytest.mark.asyncio
    async def test_metadata_includes_required_fields(
        self, service: S3StorageService, mock_minio: MagicMock
    ) -> None:
        firm_id = uuid.uuid4()
        matter_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        file_hash = "b" * 64

        await service.upload_document(
            firm_id=firm_id,
            matter_id=matter_id,
            document_id=doc_id,
            extension="pdf",
            data=BytesIO(b"x"),
            size=1,
            content_type="application/pdf",
            file_hash=file_hash,
        )

        call_kwargs = mock_minio.put_object.call_args
        metadata = call_kwargs.kwargs.get("metadata") or call_kwargs[1].get("metadata")
        assert metadata["document-id"] == str(doc_id)
        assert metadata["matter-id"] == str(matter_id)
        assert metadata["sha256"] == file_hash
        assert "ingestion-timestamp" in metadata


class TestDownloadDocument:
    @pytest.mark.asyncio
    async def test_returns_bytes_and_content_type(
        self, service: S3StorageService, mock_minio: MagicMock
    ) -> None:
        content = b"downloaded file content"
        mock_response = MagicMock()
        mock_response.read.return_value = content
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_minio.get_object.return_value = mock_response

        data, ct = await service.download_document("some/key/original.pdf")

        assert data == content
        assert ct == "application/pdf"
        mock_response.close.assert_called_once()
        mock_response.release_conn.assert_called_once()


class TestDeleteDocument:
    @pytest.mark.asyncio
    async def test_calls_remove_object(
        self, service: S3StorageService, mock_minio: MagicMock
    ) -> None:
        key = "firm/matter/doc/original.pdf"
        await service.delete_document(key)
        mock_minio.remove_object.assert_called_once_with("gideon", key)
