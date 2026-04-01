"""Celery task for document ingestion — full pipeline orchestration.

Downloads from S3, extracts text via Tika, chunks the text, generates
embeddings via Ollama, and upserts vectors to Qdrant with permission
metadata.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from celery import shared_task  # type: ignore[import-untyped]
from opentelemetry import trace
from opentelemetry.trace import StatusCode
from shared.models.enums import IngestionStatus
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.embedding.service import EmbeddingService
from app.vectorstore.service import QdrantVectorStore

if TYPE_CHECKING:
    from app.embedding.models import EmbeddingResult
    from app.extraction.models import ExtractionResult

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


async def _update_ingestion_status(document_id: str, status: IngestionStatus) -> None:
    """Persist ingestion status to the database.

    Creates a fresh async engine per call (same pattern as
    ``_run_metadata_lookup``) to avoid event-loop conflicts.
    """
    from app.db.models.document import Document

    engine = create_async_engine(settings.db.url, pool_pre_ping=True)
    try:
        async with AsyncSession(engine) as session:
            doc = await session.get(Document, document_id)
            if doc is not None:
                doc.ingestion_status = status
                await session.commit()
    finally:
        await engine.dispose()


@shared_task(name="opencase.ingest_document")  # type: ignore[untyped-decorator]
def ingest_document(document_id: str, s3_key: str) -> dict[str, object]:
    """Ingest a document — extract, chunk, embed, and upsert to Qdrant.

    Args:
        document_id: UUID string of the document record.
        s3_key: S3 object key where the original file is stored.

    Returns:
        Status dict with pipeline results.
    """
    logger.info("ingest_document: %s at %s", document_id, s3_key)
    return asyncio.run(_ingest(document_id, s3_key))


async def _ingest(document_id: str, s3_key: str) -> dict[str, object]:
    with tracer.start_as_current_span(
        "ingest_document",
        record_exception=False,
        attributes={
            "document.id": document_id,
            "document.s3_key": s3_key,
        },
    ) as span:
        try:
            s3_prefix = s3_key.rsplit("/", 1)[0]

            await _update_ingestion_status(document_id, IngestionStatus.extracting)
            result = await _run_extract(document_id, s3_key, s3_prefix, span)
            payload_metadata = await _run_metadata_lookup(document_id)

            await _update_ingestion_status(document_id, IngestionStatus.chunking)
            chunks_data = await _run_chunking(document_id, result.text, s3_prefix, span)

            await _update_ingestion_status(document_id, IngestionStatus.embedding)
            point_count = await _run_embedding(chunks_data, payload_metadata, span)

            await _update_ingestion_status(document_id, IngestionStatus.indexed)

            logger.info(
                "ingest_document done: %s (%d chunks, %d points)",
                document_id,
                len(chunks_data),
                point_count,
            )
            return {
                "status": "completed",
                "document_id": document_id,
                "text_length": len(result.text),
                "chunk_count": len(chunks_data),
                "point_count": point_count,
            }

        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            try:
                await _update_ingestion_status(document_id, IngestionStatus.failed)
            except Exception:
                logger.exception(
                    "Failed to update ingestion status to 'failed' for %s",
                    document_id,
                )
            raise


async def _run_extract(
    document_id: str,
    s3_key: str,
    s3_prefix: str,
    span: trace.Span,
) -> ExtractionResult:
    """Download from S3, extract text via Tika, persist extracted.json."""
    from app.extraction import get_extraction_service
    from app.storage import get_storage_service

    storage = get_storage_service()

    with tracer.start_as_current_span("ingestion.s3_download"):
        file_bytes, content_type = await storage.download_document(s3_key)

    filename = s3_key.rsplit("/", 1)[-1]
    extraction = get_extraction_service()
    result = await extraction.extract_text(file_bytes, filename, content_type)

    extracted_key = f"{s3_prefix}/extracted.json"
    with tracer.start_as_current_span("ingestion.s3_upload"):
        await storage.upload_json(key=extracted_key, data=result.to_dict())

    span.set_attribute("extraction.text_length", len(result.text))
    span.set_attribute("ingestion.extracted_key", extracted_key)

    logger.info(
        "ingest_document extracted: %s (%d chars, persisted to %s)",
        document_id,
        len(result.text),
        extracted_key,
    )
    return result


async def _run_metadata_lookup(document_id: str) -> dict[str, object]:
    """Query Document + Matter from DB to build the Qdrant payload metadata.

    Creates a fresh async engine per call to avoid the "Future attached to a
    different loop" error that occurs when Celery's ``asyncio.run()`` creates
    a new event loop but the module-level engine is bound to an old one.
    """
    from app.db.models.document import Document
    from app.db.models.matter import Matter

    engine = create_async_engine(settings.db.url, pool_pre_ping=True)

    try:
        with tracer.start_as_current_span("ingestion.db_lookup"):
            async with AsyncSession(engine) as session:
                doc = await session.get(Document, document_id)
                if doc is None:
                    msg = f"Document {document_id} not found in database"
                    raise ValueError(msg)

                matter = await session.get(Matter, doc.matter_id)
                if matter is None:
                    msg = f"Matter {doc.matter_id} not found in database"
                    raise ValueError(msg)
    finally:
        await engine.dispose()

    return {
        "firm_id": str(doc.firm_id),
        "matter_id": str(doc.matter_id),
        "client_id": str(matter.client_id),
        "classification": str(doc.classification),
        "source": str(doc.source),
        "bates_number": doc.bates_number,
        "page_number": None,  # populated per-chunk in future page-aware extraction
    }


async def _run_chunking(
    document_id: str,
    text: str,
    s3_prefix: str,
    span: trace.Span,
) -> list[dict[str, object]]:
    """Split text into chunks and persist chunks.json to S3."""
    from app.chunking import get_chunking_service
    from app.storage import get_storage_service

    with tracer.start_as_current_span("ingestion.chunk"):
        chunking = get_chunking_service()
        chunks = chunking.chunk_text(text, document_id, {})
        chunks_data: list[dict[str, object]] = [c.to_dict() for c in chunks]

        storage = get_storage_service()
        await storage.upload_json(
            key=f"{s3_prefix}/chunks.json",
            data={"document_id": document_id, "chunks": chunks_data},
        )

    span.set_attribute("chunking.chunk_count", len(chunks))

    logger.info(
        "ingest_document chunked: %s (%d chunks)",
        document_id,
        len(chunks),
    )
    return chunks_data


async def _run_embedding(
    chunks_data: list[dict[str, object]],
    payload_metadata: dict[str, object],
    span: trace.Span,
) -> int:
    """Embed chunks via Ollama and upsert vectors to Qdrant.

    Creates fresh service instances per call to avoid event-loop
    conflicts in Celery workers (each ``asyncio.run()`` creates a
    new loop, but singleton clients hold connections bound to
    the previous one).
    """
    with tracer.start_as_current_span("ingestion.embed_upsert"):
        embedding_service = EmbeddingService(settings.embedding)
        embeddings: list[EmbeddingResult] = await embedding_service.embed_chunks(
            chunks_data
        )

        vectorstore = QdrantVectorStore(settings.qdrant, settings.embedding)
        try:
            point_count = await vectorstore.upsert_vectors(embeddings, payload_metadata)
        finally:
            await vectorstore.close()

    span.set_attribute("embedding.result_count", len(embeddings))
    span.set_attribute("vectorstore.point_count", point_count)

    return point_count
