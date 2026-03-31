"""Chunk result model returned by chunking services."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ChunkResult:
    """Immutable result of a single text chunk.

    Attributes:
        document_id: UUID string of the source document.
        chunk_index: Zero-based position of this chunk in the document.
        text: The chunk text content.
        char_start: Character offset of the chunk start in the original text.
        char_end: Character offset of the chunk end (exclusive) in the
            original text, such that ``original[char_start:char_end] == text``.
        metadata: Pass-through metadata dict from the caller.
    """

    document_id: str
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-compatible dict for Celery task results."""
        return {
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "metadata": self.metadata,
        }
