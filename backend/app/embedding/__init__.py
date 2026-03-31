"""Embedding module — vector embedding generation for document chunks."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.embedding.service import EmbeddingService

_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Return the EmbeddingService singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        from app.core.config import settings
        from app.embedding.service import EmbeddingService

        _service = EmbeddingService(settings.embedding)
    return _service
