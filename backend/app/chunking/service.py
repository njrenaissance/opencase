"""Chunking service — splits extracted text into overlapping chunks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.chunking.models import ChunkResult
from app.chunking.strategies import ChunkingStrategy, RecursiveStrategy

if TYPE_CHECKING:
    from app.core.config import ChunkingSettings

logger = logging.getLogger(__name__)

STRATEGY_MAP: dict[str, type[ChunkingStrategy]] = {
    "recursive": RecursiveStrategy,
}


class ChunkingService:
    """Splits document text into overlapping chunks with character offsets.

    The active splitting strategy is selected by
    :pyattr:`ChunkingSettings.strategy` and looked up in
    :data:`STRATEGY_MAP`.
    """

    def __init__(self, settings: ChunkingSettings) -> None:
        strategy_cls = STRATEGY_MAP.get(settings.strategy)
        if strategy_cls is None:
            msg = (
                f"Unknown chunking strategy: {settings.strategy!r}. "
                f"Available: {', '.join(sorted(STRATEGY_MAP))}"
            )
            raise ValueError(msg)
        # All concrete strategies accept ChunkingSettings; the Protocol
        # does not declare __init__, so mypy cannot verify the call.
        self._strategy: ChunkingStrategy = strategy_cls(settings)  # type: ignore[call-arg]

    def chunk_text(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, object] | None = None,
    ) -> list[ChunkResult]:
        """Split *text* into chunks with character offsets.

        Args:
            text: The full document text to chunk.
            document_id: UUID string of the source document.
            metadata: Optional pass-through metadata attached to every chunk.

        Returns:
            List of :class:`ChunkResult` instances.  Returns an empty list
            when *text* is empty or whitespace-only.
        """
        if not text or not text.strip():
            return []

        meta = metadata or {}
        chunks = self._strategy.split(text)
        offsets = self._compute_offsets(text, chunks)

        return [
            ChunkResult(
                document_id=document_id,
                chunk_index=i,
                text=chunk,
                char_start=start,
                char_end=end,
                metadata=dict(meta),
            )
            for i, (chunk, (start, end)) in enumerate(zip(chunks, offsets, strict=True))
        ]

    @staticmethod
    def _compute_offsets(text: str, chunks: list[str]) -> list[tuple[int, int]]:
        """Recover character offsets for each chunk in the original text.

        The splitter returns only strings.  We locate each chunk via
        ``str.find`` with a forward-advancing search cursor.  The cursor
        advances by ``char_start + 1`` (not ``char_end``) so that
        overlapping chunks are found correctly — chunk *N+1* may start
        before chunk *N* ends.
        """
        offsets: list[tuple[int, int]] = []
        search_start = 0
        for chunk in chunks:
            idx = text.find(chunk, search_start)
            if idx == -1:
                # Fallback: splitter may have stripped whitespace causing
                # the chunk to not be findable from search_start.
                idx = text.find(chunk)
            if idx == -1:
                # Last resort: use current search position.  This should
                # not happen in practice — log so mismatches are visible.
                logger.warning(
                    "chunk not found in source text, using fallback offset %d",
                    search_start,
                )
                idx = search_start
            char_start = idx
            char_end = idx + len(chunk)
            offsets.append((char_start, char_end))
            search_start = char_start + 1
        return offsets
