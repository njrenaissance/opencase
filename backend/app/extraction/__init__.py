"""Extraction module — document text extraction via Apache Tika."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.extraction.tika import TikaExtractionService

_service: TikaExtractionService | None = None


def get_extraction_service() -> TikaExtractionService:
    """Return the TikaExtractionService singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        from app.core.config import settings
        from app.extraction.tika import TikaExtractionService

        _service = TikaExtractionService(settings.extraction)
    return _service
