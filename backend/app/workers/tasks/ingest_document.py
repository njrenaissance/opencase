"""Celery task for document ingestion — orchestrates extraction and storage.

Downloads from S3, extracts text via Tika, and persists the extraction
result as ``extracted.json`` alongside the original document.  Future
steps (chunking, embedding, Qdrant upsert) will be added here.
"""

from __future__ import annotations

import asyncio
import logging

from celery import shared_task  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


@shared_task(name="opencase.ingest_document")  # type: ignore[untyped-decorator]
def ingest_document(document_id: str, s3_key: str) -> dict[str, str]:
    """Ingest a document — extract text and persist result to S3.

    Args:
        document_id: UUID string of the document record.
        s3_key: S3 object key where the original file is stored.

    Returns:
        Status dict with ``{"status": "extracted", "document_id": ...}``.
    """
    logger.info("ingest_document: %s at %s", document_id, s3_key)
    return asyncio.run(_ingest(document_id, s3_key))


async def _ingest(document_id: str, s3_key: str) -> dict[str, str]:
    from app.extraction import get_extraction_service
    from app.storage import get_storage_service

    storage = get_storage_service()
    extraction = get_extraction_service()

    # 1. Download original from S3
    file_bytes, content_type = await storage.download_document(s3_key)
    filename = s3_key.rsplit("/", 1)[-1]

    # 2. Extract text via Tika
    result = await extraction.extract_text(file_bytes, filename, content_type)

    # 3. Persist extracted.json to S3 alongside the original
    # S3 key pattern: {firm_id}/{matter_id}/{document_id}/original.{ext}
    parts = s3_key.split("/")
    extracted_key = f"{parts[0]}/{parts[1]}/{parts[2]}/extracted.json"
    await storage.upload_json(key=extracted_key, data=result.to_dict())

    logger.info(
        "ingest_document done: %s (%d chars extracted, persisted to %s)",
        document_id,
        len(result.text),
        extracted_key,
    )

    # Future steps: chunking, embedding, Qdrant upsert
    return {"status": "extracted", "document_id": document_id}
