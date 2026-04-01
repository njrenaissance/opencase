"""Embedding service — generates vector embeddings via Ollama."""

from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

import httpx
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from app.core.metrics import (
    embedding_batch_count,
    embedding_chunks_processed,
    embedding_completed,
    embedding_duration_seconds,
    embedding_failed,
)
from app.embedding.models import EmbeddingResult

if TYPE_CHECKING:
    from app.core.config import EmbeddingSettings

tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


class EmbeddingDimensionError(ValueError):
    """Raised when Ollama returns vectors with unexpected dimensions."""


class EmbeddingService:
    """Generate vector embeddings for text chunks using Ollama.

    Args:
        settings: EmbeddingSettings with model, base_url, dimensions,
            batch_size, and request_timeout.
    """

    def __init__(self, settings: EmbeddingSettings) -> None:
        self._settings = settings

    async def embed_chunks(
        self, chunks: list[dict[str, object]]
    ) -> list[EmbeddingResult]:
        """Embed a list of chunk dicts and return EmbeddingResult objects.

        Each chunk dict must have ``document_id``, ``chunk_index``, ``text``,
        and optionally ``metadata``.

        Chunks are batched according to ``EmbeddingSettings.batch_size`` to
        avoid overwhelming Ollama with a single massive request.

        Args:
            chunks: List of chunk dicts (as produced by ChunkResult.to_dict()).

        Returns:
            List of EmbeddingResult objects, one per input chunk.

        Raises:
            EmbeddingDimensionError: If Ollama returns vectors whose
                dimensions do not match ``EmbeddingSettings.dimensions``.
            httpx.HTTPStatusError: If Ollama returns a non-2xx response.
            httpx.ConnectError: If Ollama is unreachable.
        """
        if not chunks:
            return []

        _required_keys = {"document_id", "chunk_index", "text"}
        for i, chunk in enumerate(chunks):
            missing = _required_keys - chunk.keys()
            if missing:
                msg = f"Chunk at index {i} missing keys: {sorted(missing)}"
                raise ValueError(msg)

        batch_size = self._settings.batch_size
        num_batches = math.ceil(len(chunks) / batch_size)

        with tracer.start_as_current_span(
            "embedding.embed_chunks",
            attributes={
                "embedding.chunk_count": len(chunks),
                "embedding.model": self._settings.model,
                "embedding.batch_size": batch_size,
            },
        ) as span:
            start_time = time.monotonic()
            try:
                results: list[EmbeddingResult] = []

                async with httpx.AsyncClient(
                    base_url=self._settings.base_url,
                    timeout=self._settings.request_timeout,
                ) as client:
                    for batch_start in range(0, len(chunks), batch_size):
                        batch = chunks[batch_start : batch_start + batch_size]
                        texts = [str(c["text"]) for c in batch]

                        response = await client.post(
                            "/api/embed",
                            json={
                                "model": self._settings.model,
                                "input": texts,
                            },
                        )
                        response.raise_for_status()

                        data = response.json()
                        vectors: list[list[float]] = data["embeddings"]

                        if len(vectors) != len(batch):
                            msg = (
                                f"Ollama returned {len(vectors)} vectors "
                                f"for {len(batch)} inputs"
                            )
                            raise EmbeddingDimensionError(msg)

                        for chunk, vector in zip(batch, vectors, strict=True):
                            if len(vector) != self._settings.dimensions:
                                msg = (
                                    f"Expected {self._settings.dimensions} "
                                    f"dimensions, got {len(vector)}"
                                )
                                raise EmbeddingDimensionError(msg)

                            results.append(
                                EmbeddingResult(
                                    document_id=str(chunk["document_id"]),
                                    chunk_index=int(chunk["chunk_index"]),  # type: ignore[call-overload]
                                    vector=vector,
                                    text=str(chunk["text"]),
                                    metadata=dict(chunk.get("metadata") or {}),  # type: ignore[call-overload]
                                )
                            )

                span.set_attribute("embedding.result_count", len(results))
                span.set_attribute("embedding.batch_count", num_batches)

                elapsed = time.monotonic() - start_time
                attrs = {"model": self._settings.model}
                embedding_completed.add(1, attrs)
                embedding_duration_seconds.record(elapsed, attrs)
                embedding_chunks_processed.record(len(chunks), attrs)
                embedding_batch_count.record(num_batches, attrs)

                logger.info(
                    "Embedded %d chunks in %d batch(es) using %s",
                    len(results),
                    num_batches,
                    self._settings.model,
                )
                return results

            except Exception as exc:
                elapsed = time.monotonic() - start_time
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                embedding_failed.add(
                    1,
                    {
                        "model": self._settings.model,
                        "error_type": type(exc).__name__,
                    },
                )
                embedding_duration_seconds.record(
                    elapsed, {"model": self._settings.model}
                )
                raise
