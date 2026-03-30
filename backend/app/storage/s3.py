"""S3StorageService — async wrapper around minio-py for document storage."""

from __future__ import annotations

import asyncio
import io
import json
import uuid
from datetime import UTC, datetime
from typing import BinaryIO

from minio import Minio
from opentelemetry import trace

from app.core.config import S3Settings

tracer = trace.get_tracer(__name__)


class S3StorageService:
    """Wraps minio-py with the OpenCase bucket layout convention.

    Bucket key pattern::

        {firm_id}/{matter_id}/{document_id}/original.{ext}
    """

    def __init__(self, s3_settings: S3Settings) -> None:
        self._client = Minio(
            s3_settings.endpoint,
            access_key=s3_settings.access_key,
            secret_key=s3_settings.secret_key,
            secure=s3_settings.use_ssl,
            region=s3_settings.region,
        )
        self._bucket = s3_settings.bucket

    # ------------------------------------------------------------------
    # Key construction
    # ------------------------------------------------------------------

    @staticmethod
    def object_key(
        firm_id: uuid.UUID,
        matter_id: uuid.UUID,
        document_id: uuid.UUID,
        extension: str,
    ) -> str:
        """Build the canonical S3 object key for a document."""
        return f"{firm_id}/{matter_id}/{document_id}/original.{extension}"

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    async def upload_document(
        self,
        *,
        firm_id: uuid.UUID,
        matter_id: uuid.UUID,
        document_id: uuid.UUID,
        extension: str,
        data: BinaryIO,
        size: int,
        content_type: str,
        file_hash: str,
    ) -> str:
        """Upload a document to MinIO. Returns the object key."""
        with tracer.start_as_current_span(
            "s3.upload_document",
            attributes={
                "document.id": str(document_id),
                "s3.bucket": self._bucket,
                "s3.size_bytes": size,
            },
        ):
            key = self.object_key(firm_id, matter_id, document_id, extension)
            metadata = {
                "document-id": str(document_id),
                "matter-id": str(matter_id),
                "sha256": file_hash,
                "ingestion-timestamp": datetime.now(UTC).isoformat(),
            }
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self._put_object,
                key,
                data,
                size,
                content_type,
                metadata,
            )
            return key

    def _put_object(
        self,
        key: str,
        data: BinaryIO,
        size: int,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        self._client.put_object(
            self._bucket,
            key,
            data,
            length=size,
            content_type=content_type,
            metadata=metadata,  # type: ignore[arg-type]  # minio expects wider union
        )

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    async def download_document(self, key: str) -> tuple[bytes, str]:
        """Download a document from MinIO. Returns ``(file_bytes, content_type)``."""
        with tracer.start_as_current_span(
            "s3.download_document",
            attributes={"s3.key": key, "s3.bucket": self._bucket},
        ):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._get_object, key)

    def _get_object(self, key: str) -> tuple[bytes, str]:
        response = self._client.get_object(self._bucket, key)
        try:
            data = response.read()
            ct = response.headers.get("Content-Type", "application/octet-stream")
        finally:
            response.close()
            response.release_conn()
        return data, ct

    # ------------------------------------------------------------------
    # Delete (cleanup on failed commits)
    # ------------------------------------------------------------------

    async def delete_document(self, key: str) -> None:
        """Delete an object from MinIO."""
        with tracer.start_as_current_span(
            "s3.delete_document",
            attributes={"s3.key": key, "s3.bucket": self._bucket},
        ):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._remove_object, key)

    def _remove_object(self, key: str) -> None:
        self._client.remove_object(self._bucket, key)

    # ------------------------------------------------------------------
    # JSON artifact upload (extracted text, future chunk data, etc.)
    # ------------------------------------------------------------------

    @staticmethod
    def extracted_key(
        firm_id: uuid.UUID,
        matter_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> str:
        """Build the S3 key for a document's extracted text artifact."""
        return f"{firm_id}/{matter_id}/{document_id}/extracted.json"

    async def upload_json(self, *, key: str, data: dict[str, object]) -> None:
        """Upload a JSON-serializable dict as an S3 object."""
        with tracer.start_as_current_span(
            "s3.upload_json",
            attributes={"s3.key": key, "s3.bucket": self._bucket},
        ):
            payload = json.dumps(data, ensure_ascii=False).encode()
            buf = io.BytesIO(payload)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self._put_object,
                key,
                buf,
                len(payload),
                "application/json",
                {},
            )
