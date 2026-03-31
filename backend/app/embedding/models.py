"""Embedding result model returned by embedding services."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """Immutable result of embedding a single text chunk.

    Attributes:
        document_id: UUID string of the source document.
        chunk_index: Zero-based position of this chunk in the document.
        vector: Embedding vector (list of floats).
        text: The original chunk text that was embedded.
        metadata: Pass-through metadata dict from the chunk.
    """

    document_id: str
    chunk_index: int
    vector: list[float]
    text: str
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-compatible dict for Celery task results."""
        return {
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "vector": self.vector,
            "text": self.text,
            "metadata": self.metadata,
        }
