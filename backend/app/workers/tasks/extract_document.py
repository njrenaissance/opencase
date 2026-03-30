"""Celery task for document text extraction via Apache Tika.

Downloads the original file from S3 and extracts text + metadata
using TikaExtractionService.  Does not persist the result — the
calling task (e.g. ``ingest_document``) is responsible for storage.
"""

from __future__ import annotations

import asyncio
import logging

from celery import shared_task  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


@shared_task(name="opencase.extract_document")  # type: ignore[untyped-decorator]
def extract_document(document_id: str, s3_key: str) -> dict[str, object]:
    """Extract text from a document stored in S3.

    Args:
        document_id: UUID string of the document record.
        s3_key: S3 object key where the original file is stored.

    Returns:
        :meth:`ExtractionResult.to_dict` — a JSON-serializable dict
        with ``text``, ``content_type``, ``metadata``, ``ocr_applied``,
        and ``language`` keys.
    """
    logger.info("extract_document: %s at %s", document_id, s3_key)
    return asyncio.run(_extract(document_id, s3_key))


async def _extract(document_id: str, s3_key: str) -> dict[str, object]:
    from app.extraction import get_extraction_service
    from app.storage import get_storage_service

    storage = get_storage_service()
    extraction = get_extraction_service()

    file_bytes, content_type = await storage.download_document(s3_key)
    filename = s3_key.rsplit("/", 1)[-1]

    result = await extraction.extract_text(file_bytes, filename, content_type)
    logger.info(
        "extract_document done: %s (%d chars, ocr=%s)",
        document_id,
        len(result.text),
        result.ocr_applied,
    )
    return result.to_dict()
