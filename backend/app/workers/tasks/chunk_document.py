"""Celery task for document text chunking.

Splits extracted text into overlapping chunks and persists the result
to S3 as ``chunks.json`` alongside the original and extracted artifacts.
"""

from __future__ import annotations

import asyncio
import logging

from celery import shared_task  # type: ignore[import-untyped]
from opentelemetry import trace
from opentelemetry.trace import StatusCode

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@shared_task(name="opencase.chunk_document")  # type: ignore[untyped-decorator]
def chunk_document(
    document_id: str,
    text: str,
    metadata: dict[str, object],
    s3_prefix: str,
) -> dict[str, object]:
    """Split extracted text into overlapping chunks.

    Args:
        document_id: UUID string of the document record.
        text: Full extracted text to chunk.
        metadata: Pass-through metadata attached to every chunk.
        s3_prefix: S3 key prefix (e.g. ``firm/matter/doc``) where
            ``chunks.json`` will be persisted.

    Returns:
        Dict with ``document_id``, ``chunk_count``, and ``chunks``
        (list of :meth:`ChunkResult.to_dict` dicts).
    """
    logger.info("chunk_document: %s", document_id)
    return asyncio.run(_chunk(document_id, text, metadata, s3_prefix))


async def _chunk(
    document_id: str,
    text: str,
    metadata: dict[str, object],
    s3_prefix: str,
) -> dict[str, object]:
    from app.chunking import get_chunking_service
    from app.storage import get_storage_service

    with tracer.start_as_current_span(
        "chunk_document",
        record_exception=False,
        attributes={"document.id": document_id},
    ) as span:
        try:
            service = get_chunking_service()
            chunks = service.chunk_text(text, document_id, metadata)

            span.set_attribute("chunking.chunk_count", len(chunks))
            span.set_attribute("chunking.text_length", len(text))

            # Persist chunks.json to S3
            chunks_key = f"{s3_prefix}/chunks.json"
            chunks_data: list[dict[str, object]] = [c.to_dict() for c in chunks]
            storage = get_storage_service()
            await storage.upload_json(
                key=chunks_key,
                data={"document_id": document_id, "chunks": chunks_data},
            )

            logger.info(
                "chunk_document done: %s (%d chunks)",
                document_id,
                len(chunks),
            )
            return {
                "document_id": document_id,
                "chunk_count": len(chunks),
                "chunks": chunks_data,
            }

        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise
