"""Embedding module — vector embedding generation for document chunks.

The singleton returned by ``get_embedding_service()`` is intended for
use within FastAPI (single process, single event loop). Celery tasks
create fresh instances per call to avoid async event-loop conflicts
(see ``ingest_document._run_embedding``).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.embedding.service import EmbeddingService

_service: EmbeddingService | None = None
_lock = threading.Lock()


def get_embedding_service() -> EmbeddingService:
    """Return the EmbeddingService singleton (thread-safe)."""
    global _service  # noqa: PLW0603
    if _service is None:
        with _lock:
            if _service is None:
                from app.core.config import settings
                from app.embedding.service import EmbeddingService

                _service = EmbeddingService(settings.embedding)
    return _service
