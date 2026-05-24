"""Chunking service — splits extracted text into overlapping chunks."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from app.chunking.models import ChunkResult
from app.chunking.strategies import ChunkingStrategy, RecursiveStrategy
from app.core.metrics import (
    chunking_chunks_produced,
    chunking_completed,
    chunking_duration_seconds,
    chunking_failed,
    chunking_text_length_chars,
)

if TYPE_CHECKING:
    from app.core.config import ChunkingSettings

tracer = trace.get_tracer(__name__)
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
        self._chunk_size = settings.chunk_size
        # Minimum chunk size — smaller chunks are merged with adjacent chunks.
        # Only apply if min_chunk_size < chunk_size (don't merge if it would
        # create chunks larger than the target chunk_size).
        self._min_chunk_size = min(settings.min_chunk_size, settings.chunk_size)

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

        strategy_name = type(self._strategy).__name__
        start_time = time.monotonic()

        with tracer.start_as_current_span(
            "chunking.chunk_text",
            attributes={
                "chunking.document_id": document_id,
                "chunking.text_length": len(text),
                "chunking.strategy": strategy_name,
            },
        ) as span:
            try:
                meta = metadata or {}
                chunks = self._strategy.split(text)
                offsets = self._compute_offsets(text, chunks)
                # Merge small chunks to avoid fragmentation (only if chunk_size
                # is large enough that merging won't dominate). Pass chunks and
                # offsets to merge function, which returns merged offset ranges.
                if self._chunk_size >= self._min_chunk_size:
                    merged_offsets = self._merge_small_chunks_offsets(offsets)
                else:
                    merged_offsets = offsets
                # Extract actual text from original using merged offsets
                merged_chunks = [text[s:e] for s, e in merged_offsets]

                results = [
                    ChunkResult(
                        document_id=document_id,
                        chunk_index=i,
                        text=chunk,
                        char_start=start,
                        char_end=end,
                        metadata=dict(meta),
                    )
                    for i, (chunk, (start, end)) in enumerate(
                        zip(merged_chunks, merged_offsets, strict=True)
                    )
                ]

                span.set_attribute("chunking.chunk_count", len(results))

                elapsed = time.monotonic() - start_time
                attrs = {"strategy": strategy_name}
                chunking_completed.add(1, attrs)
                chunking_duration_seconds.record(elapsed, attrs)
                chunking_text_length_chars.record(len(text), attrs)
                chunking_chunks_produced.record(len(results), attrs)

                return results

            except Exception as exc:
                elapsed = time.monotonic() - start_time
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                chunking_failed.add(1, {"error_type": type(exc).__name__})
                chunking_duration_seconds.record(elapsed, {"strategy": strategy_name})
                raise

    def _merge_small_chunks_offsets(
        self, offsets: list[tuple[int, int]]
    ) -> list[tuple[int, int]]:
        """Merge offset ranges for chunks smaller than min_chunk_size.

        Returns merged offset ranges that can be used to extract text from
        the original source. Merging is cascading—if a merged range is still
        smaller than min_chunk_size, it continues merging with the next
        range.

        Args:
            offsets: List of (char_start, char_end) offset tuples.

        Returns:
            List of merged offset ranges.
        """
        if not offsets:
            return offsets

        merged: list[tuple[int, int]] = []
        i = 0
        while i < len(offsets):
            start, end = offsets[i]
            size = end - start

            # Keep merging with next offset while too small (unless last)
            while size < self._min_chunk_size and i + 1 < len(offsets):
                next_start, next_end = offsets[i + 1]
                # Extend range to include next chunk
                end = next_end
                size = end - start
                i += 1

            merged.append((start, end))
            i += 1

        return merged

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
