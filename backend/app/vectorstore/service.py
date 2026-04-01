"""Qdrant vector store service — upsert and delete document vectors."""

from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from qdrant_client import AsyncQdrantClient, models

from app.core.metrics import (
    vectorstore_delete_completed,
    vectorstore_delete_duration_seconds,
    vectorstore_upsert_completed,
    vectorstore_upsert_duration_seconds,
    vectorstore_upsert_failed,
    vectorstore_upsert_points,
)
from app.embedding.models import EmbeddingResult
from app.vectorstore.models import (
    REQUIRED_METADATA_KEYS,
    VectorPayload,
    make_point_id,
)

if TYPE_CHECKING:
    from app.core.config import EmbeddingSettings, QdrantSettings

tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

# Max points per Qdrant upsert call. Independent of EmbeddingSettings.batch_size
# (which controls Ollama HTTP request batching). Qdrant handles larger batches
# efficiently, but 100 keeps memory usage bounded during serialization.
_UPSERT_BATCH_SIZE = 100


class QdrantVectorStore:
    """Manage document vectors in a Qdrant collection.

    Args:
        qdrant_settings: Connection and collection configuration.
        embedding_settings: Used for vector dimension info.
    """

    def __init__(
        self,
        qdrant_settings: QdrantSettings,
        embedding_settings: EmbeddingSettings,
    ) -> None:
        self._settings = qdrant_settings
        self._embedding_settings = embedding_settings
        self._collection = qdrant_settings.collection

        if qdrant_settings.prefer_grpc:
            self._client = AsyncQdrantClient(
                host=qdrant_settings.host,
                port=qdrant_settings.port,
                grpc_port=qdrant_settings.grpc_port,
                prefer_grpc=True,
                https=qdrant_settings.use_ssl,
                api_key=qdrant_settings.api_key,
            )
        else:
            self._client = AsyncQdrantClient(
                url=qdrant_settings.url,
                api_key=qdrant_settings.api_key,
            )

    async def upsert_vectors(
        self,
        embeddings: list[EmbeddingResult],
        payload_metadata: dict[str, object],
    ) -> int:
        """Build Qdrant points from embeddings and upsert them.

        Args:
            embeddings: Embedding results from Ollama.
            payload_metadata: Document-level metadata containing at
                least the keys in ``REQUIRED_METADATA_KEYS`` plus
                optional ``bates_number`` and ``page_number``.

        Returns:
            Number of points upserted.

        Raises:
            ValueError: If ``payload_metadata`` is missing required keys.
        """
        missing = REQUIRED_METADATA_KEYS - payload_metadata.keys()
        if missing:
            msg = f"payload_metadata missing required keys: {sorted(missing)}"
            raise ValueError(msg)

        if not embeddings:
            return 0

        with tracer.start_as_current_span(
            "vectorstore.upsert_vectors",
            attributes={
                "vectorstore.collection": self._collection,
                "vectorstore.point_count": len(embeddings),
                "vectorstore.batch_count": math.ceil(
                    len(embeddings) / _UPSERT_BATCH_SIZE
                ),
            },
        ) as span:
            start_time = time.monotonic()
            try:
                points = [
                    self._build_point(emb, payload_metadata) for emb in embeddings
                ]

                for batch_start in range(0, len(points), _UPSERT_BATCH_SIZE):
                    batch = points[batch_start : batch_start + _UPSERT_BATCH_SIZE]
                    await self._client.upsert(
                        collection_name=self._collection,
                        points=batch,
                    )

                elapsed = time.monotonic() - start_time
                attrs = {"collection": self._collection}
                vectorstore_upsert_completed.add(1, attrs)
                vectorstore_upsert_duration_seconds.record(elapsed, attrs)
                vectorstore_upsert_points.record(len(points), attrs)

                logger.info(
                    "Upserted %d points into collection %r",
                    len(points),
                    self._collection,
                )
                return len(points)

            except Exception as exc:
                elapsed = time.monotonic() - start_time
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                vectorstore_upsert_failed.add(
                    1,
                    {
                        "collection": self._collection,
                        "error_type": type(exc).__name__,
                    },
                )
                vectorstore_upsert_duration_seconds.record(
                    elapsed, {"collection": self._collection}
                )
                raise

    async def delete_by_document(self, document_id: str) -> int:
        """Delete all points belonging to a document.

        Args:
            document_id: UUID string of the document.

        Returns:
            Number of points deleted (best-effort count via scroll).
        """
        with tracer.start_as_current_span(
            "vectorstore.delete_by_document",
            attributes={
                "vectorstore.collection": self._collection,
                "vectorstore.document_id": document_id,
            },
        ) as span:
            start_time = time.monotonic()
            try:
                # Count before delete so we can report how many were removed.
                scroll_result = await self._client.scroll(
                    collection_name=self._collection,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id),
                            )
                        ]
                    ),
                    limit=10_000,
                )
                count = len(scroll_result[0])

                await self._client.delete(
                    collection_name=self._collection,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="document_id",
                                    match=models.MatchValue(value=document_id),
                                )
                            ]
                        )
                    ),
                )

                span.set_attribute("vectorstore.deleted_count", count)

                elapsed = time.monotonic() - start_time
                attrs = {"collection": self._collection}
                vectorstore_delete_completed.add(1, attrs)
                vectorstore_delete_duration_seconds.record(elapsed, attrs)

                logger.info(
                    "Deleted %d points for document %s from collection %r",
                    count,
                    document_id,
                    self._collection,
                )
                return count

            except Exception as exc:
                elapsed = time.monotonic() - start_time
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                vectorstore_delete_duration_seconds.record(
                    elapsed, {"collection": self._collection}
                )
                raise

    async def close(self) -> None:
        """Close the underlying Qdrant client connection."""
        await self._client.close()

    @staticmethod
    def _build_point(
        emb: EmbeddingResult,
        payload_metadata: dict[str, object],
    ) -> models.PointStruct:
        """Build a single Qdrant PointStruct from an embedding result."""
        payload: VectorPayload = {
            "firm_id": str(payload_metadata["firm_id"]),
            "matter_id": str(payload_metadata["matter_id"]),
            "client_id": str(payload_metadata["client_id"]),
            "document_id": emb.document_id,
            "chunk_index": emb.chunk_index,
            "classification": str(payload_metadata["classification"]),
            "source": str(payload_metadata["source"]),
            "bates_number": payload_metadata.get("bates_number"),  # type: ignore[typeddict-item]
            "page_number": payload_metadata.get("page_number"),  # type: ignore[typeddict-item]
        }

        return models.PointStruct(
            id=make_point_id(emb.document_id, emb.chunk_index),
            vector=emb.vector,
            payload=payload,  # type: ignore[arg-type]
        )
