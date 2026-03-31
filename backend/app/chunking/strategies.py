"""Chunking strategy Protocol and concrete implementations.

New strategies must implement the :class:`ChunkingStrategy` protocol
(a ``split`` method) and be registered in
:data:`app.chunking.service.STRATEGY_MAP`.
"""

from __future__ import annotations

from typing import Protocol

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import ChunkingSettings


class ChunkingStrategy(Protocol):
    """Structural interface for text chunking strategies."""

    def split(self, text: str) -> list[str]:
        """Split *text* into a list of chunk strings."""
        ...


class RecursiveStrategy:
    """Recursive character text splitting via LangChain.

    Splits on the configured separator hierarchy, respecting
    ``chunk_size`` and ``chunk_overlap`` from settings.
    """

    def __init__(self, settings: ChunkingSettings) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=settings.separators,
            strip_whitespace=True,
        )

    def split(self, text: str) -> list[str]:
        """Split *text* using recursive character splitting."""
        return self._splitter.split_text(text)
