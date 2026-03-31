"""Chunking module — text splitting for embedding and vector search."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.chunking.service import ChunkingService

_service: ChunkingService | None = None


def get_chunking_service() -> ChunkingService:
    """Return the ChunkingService singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        from app.chunking.service import ChunkingService
        from app.core.config import settings

        _service = ChunkingService(settings.chunking)
    return _service
