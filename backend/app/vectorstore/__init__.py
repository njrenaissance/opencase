"""Vector store module — Qdrant vector storage for document chunks."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.vectorstore.service import QdrantVectorStore

_service: QdrantVectorStore | None = None


def get_vectorstore_service() -> QdrantVectorStore:
    """Return the QdrantVectorStore singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        from app.core.config import settings
        from app.vectorstore.service import QdrantVectorStore

        _service = QdrantVectorStore(settings.qdrant, settings.embedding)
    return _service
