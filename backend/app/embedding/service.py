"""Embedding service — generates vector embeddings via Ollama."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import httpx

from app.embedding.models import EmbeddingResult

if TYPE_CHECKING:
    from app.core.config import EmbeddingSettings

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

        results: list[EmbeddingResult] = []
        batch_size = self._settings.batch_size

        async with httpx.AsyncClient(
            base_url=self._settings.base_url,
            timeout=self._settings.request_timeout,
        ) as client:
            for batch_start in range(0, len(chunks), batch_size):
                batch = chunks[batch_start : batch_start + batch_size]
                texts = [str(c["text"]) for c in batch]

                response = await client.post(
                    "/api/embed",
                    json={"model": self._settings.model, "input": texts},
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
                            f"Expected {self._settings.dimensions} dimensions, "
                            f"got {len(vector)}"
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

        logger.info(
            "Embedded %d chunks in %d batch(es) using %s",
            len(results),
            math.ceil(len(chunks) / batch_size),
            self._settings.model,
        )
        return results
