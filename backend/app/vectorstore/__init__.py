"""Vector store module — Qdrant vector storage for document chunks.

The singleton returned by ``get_vectorstore_service()`` is intended for
use within FastAPI (single process, single event loop). Celery tasks
create fresh instances per call to avoid async event-loop conflicts
(see ``ingest_document._run_embedding``).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.vectorstore.service import QdrantVectorStore

_service: QdrantVectorStore | None = None
_lock = threading.Lock()


def get_vectorstore_service() -> QdrantVectorStore:
    """Return the QdrantVectorStore singleton (thread-safe)."""
    global _service  # noqa: PLW0603
    if _service is None:
        with _lock:
            if _service is None:
                from app.core.config import settings
                from app.vectorstore.service import QdrantVectorStore

                _service = QdrantVectorStore(settings.qdrant, settings.embedding)
    return _service
