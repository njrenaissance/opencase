"""Extraction result model returned by extraction services."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Immutable result of a document text extraction.

    Attributes:
        text: Extracted plain text content.
        content_type: MIME type detected by the extraction service.
        metadata: Raw metadata dict from the extraction service.
        ocr_applied: Whether OCR (e.g. Tesseract) was used during extraction.
        language: Detected document language, if available.
    """

    text: str
    content_type: str
    metadata: dict[str, object] = field(default_factory=dict)
    ocr_applied: bool = False
    language: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-compatible dict for Celery task results."""
        return {
            "text": self.text,
            "content_type": self.content_type,
            "metadata": self.metadata,
            "ocr_applied": self.ocr_applied,
            "language": self.language,
        }
