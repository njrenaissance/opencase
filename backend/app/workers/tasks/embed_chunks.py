"""Celery task for embedding document chunks and upserting to Qdrant.

Takes chunked text, generates vector embeddings via Ollama, and persists
the vectors to Qdrant with full permission metadata payload.
"""

from __future__ import annotations

import asyncio
import logging

from celery import shared_task  # type: ignore[import-untyped]
from opentelemetry import trace
from opentelemetry.trace import StatusCode

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@shared_task(  # type: ignore[untyped-decorator]
    name="gideon.embed_chunks",
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,
)
def embed_chunks(
    document_id: str,
    chunks: list[dict[str, object]],
    payload_metadata: dict[str, object],
) -> dict[str, object]:
    """Embed document chunks and upsert vectors to Qdrant.

    Args:
        document_id: UUID string of the document record.
        chunks: List of chunk dicts (as produced by ChunkResult.to_dict()).
        payload_metadata: Document-level metadata for the Qdrant payload.
            Must contain at least: ``firm_id``, ``matter_id``,
            ``client_id``, ``classification``, ``source``.
            Optional: ``bates_number``, ``page_number``.

    Returns:
        Dict with ``document_id``, ``chunk_count``, and ``point_count``.
    """
    logger.info("embed_chunks: %s (%d chunks)", document_id, len(chunks))
    return asyncio.run(_embed(document_id, chunks, payload_metadata))


async def _embed(
    document_id: str,
    chunks: list[dict[str, object]],
    payload_metadata: dict[str, object],
) -> dict[str, object]:
    from app.embedding import get_embedding_service
    from app.vectorstore import get_vectorstore_service

    with tracer.start_as_current_span(
        "embed_chunks",
        record_exception=False,
        attributes={
            "document.id": document_id,
            "embedding.chunk_count": len(chunks),
        },
    ) as span:
        try:
            # Step 1: Generate embeddings via Ollama
            embedding_service = get_embedding_service()
            results = await embedding_service.embed_chunks(chunks)

            span.set_attribute("embedding.result_count", len(results))

            # Step 2: Upsert vectors to Qdrant with permission payload
            vectorstore = get_vectorstore_service()
            point_count = await vectorstore.upsert_vectors(results, payload_metadata)

            span.set_attribute("vectorstore.point_count", point_count)

            logger.info(
                "embed_chunks done: %s (%d embeddings, %d points)",
                document_id,
                len(results),
                point_count,
            )
            return {
                "document_id": document_id,
                "chunk_count": len(results),
                "point_count": point_count,
            }

        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise
