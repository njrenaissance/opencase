"""Unit tests for the chunking module."""

from __future__ import annotations

from typing import Any

import pytest

from app.chunking.models import ChunkResult
from app.chunking.service import ChunkingService
from app.chunking.strategies import RecursiveStrategy
from app.core.config import ChunkingSettings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides: Any) -> ChunkingSettings:
    defaults: dict[str, Any] = {
        "strategy": "recursive",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "separators": ["\n\n", "\n", ". ", " ", ""],
    }
    defaults.update(overrides)
    return ChunkingSettings(**defaults)


def _make_service(**overrides: Any) -> ChunkingService:
    return ChunkingService(_make_settings(**overrides))


def _long_text(n_words: int = 500) -> str:
    """Generate repeating prose long enough to produce multiple chunks."""
    sentence = "The quick brown fox jumps over the lazy dog. "
    return (sentence * n_words).strip()


# ---------------------------------------------------------------------------
# ChunkResult
# ---------------------------------------------------------------------------


class TestChunkResult:
    def test_to_dict_all_fields(self):
        result = ChunkResult(
            document_id="doc-1",
            chunk_index=0,
            text="hello",
            char_start=0,
            char_end=5,
            metadata={"case": "abc"},
        )
        d = result.to_dict()
        assert d == {
            "document_id": "doc-1",
            "chunk_index": 0,
            "text": "hello",
            "char_start": 0,
            "char_end": 5,
            "metadata": {"case": "abc"},
        }

    def test_to_dict_defaults(self):
        result = ChunkResult(
            document_id="doc-1",
            chunk_index=0,
            text="hi",
            char_start=0,
            char_end=2,
        )
        assert result.metadata == {}
        assert result.to_dict()["metadata"] == {}

    def test_frozen(self):
        result = ChunkResult(
            document_id="doc-1",
            chunk_index=0,
            text="x",
            char_start=0,
            char_end=1,
        )
        with pytest.raises(AttributeError):
            result.text = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RecursiveStrategy
# ---------------------------------------------------------------------------


class TestRecursiveStrategy:
    def test_splits_text(self):
        settings = _make_settings(chunk_size=50, chunk_overlap=10)
        strategy = RecursiveStrategy(settings)
        text = _long_text(100)
        chunks = strategy.split(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 50

    def test_empty_text(self):
        strategy = RecursiveStrategy(_make_settings())
        assert strategy.split("") == []


# ---------------------------------------------------------------------------
# ChunkingService — empty / whitespace input
# ---------------------------------------------------------------------------


class TestChunkingServiceEmpty:
    @pytest.mark.parametrize("text", ["", "   ", "\n\n\t", "  \n  "])
    def test_empty_or_whitespace_returns_empty(self, text: str):
        svc = _make_service()
        assert svc.chunk_text(text, "doc-1") == []


# ---------------------------------------------------------------------------
# ChunkingService — single chunk
# ---------------------------------------------------------------------------


class TestChunkingServiceSingleChunk:
    def test_short_text_single_chunk(self):
        svc = _make_service(chunk_size=1000)
        result = svc.chunk_text("Hello world.", "doc-1")
        assert len(result) == 1
        assert result[0].chunk_index == 0
        assert result[0].text == "Hello world."
        assert result[0].document_id == "doc-1"


# ---------------------------------------------------------------------------
# ChunkingService — multi-chunk behaviour
# ---------------------------------------------------------------------------


class TestChunkingServiceMultiChunk:
    @pytest.mark.parametrize(
        "chunk_size,chunk_overlap",
        [(100, 20), (500, 100), (50, 10)],
    )
    def test_chunk_index_contiguous(self, chunk_size: int, chunk_overlap: int):
        svc = _make_service(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        result = svc.chunk_text(_long_text(), "doc-1")
        indices = [c.chunk_index for c in result]
        assert indices == list(range(len(result)))

    @pytest.mark.parametrize(
        "chunk_size,chunk_overlap",
        [(100, 20), (500, 100), (50, 10)],
    )
    def test_char_offset_accuracy(self, chunk_size: int, chunk_overlap: int):
        text = _long_text()
        svc = _make_service(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        result = svc.chunk_text(text, "doc-1")
        assert len(result) > 1, "need multiple chunks for this test"
        for chunk in result:
            assert text[chunk.char_start : chunk.char_end] == chunk.text

    @pytest.mark.parametrize(
        "chunk_size,chunk_overlap",
        [(100, 20), (500, 100), (50, 10)],
    )
    def test_chunk_size_respected(self, chunk_size: int, chunk_overlap: int):
        svc = _make_service(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        result = svc.chunk_text(_long_text(), "doc-1")
        for chunk in result:
            assert len(chunk.text) <= chunk_size

    def test_overlap_present(self):
        svc = _make_service(chunk_size=100, chunk_overlap=20)
        result = svc.chunk_text(_long_text(), "doc-1")
        assert len(result) >= 3, "need several chunks to verify overlap"
        # The tail of chunk N should appear as a substring in chunk N+1
        for i in range(len(result) - 1):
            tail = result[i].text[-20:]
            assert tail in result[i + 1].text, (
                f"tail of chunk {i} not found in chunk {i + 1}"
            )

    def test_offsets_monotonically_non_decreasing(self):
        svc = _make_service(chunk_size=100, chunk_overlap=20)
        result = svc.chunk_text(_long_text(), "doc-1")
        for i in range(1, len(result)):
            assert result[i].char_start >= result[i - 1].char_start


# ---------------------------------------------------------------------------
# ChunkingService — metadata & document_id
# ---------------------------------------------------------------------------


class TestChunkingServiceMetadata:
    def test_metadata_passthrough(self):
        meta = {"case_id": "123", "source": "government_production"}
        svc = _make_service(chunk_size=100, chunk_overlap=10)
        result = svc.chunk_text(_long_text(), "doc-1", meta)
        for chunk in result:
            assert chunk.metadata == meta

    def test_document_id_propagated(self):
        svc = _make_service(chunk_size=100, chunk_overlap=10)
        result = svc.chunk_text(_long_text(), "doc-42")
        for chunk in result:
            assert chunk.document_id == "doc-42"

    def test_none_metadata_defaults_to_empty_dict(self):
        svc = _make_service()
        result = svc.chunk_text("Hello world.", "doc-1", None)
        assert result[0].metadata == {}


# ---------------------------------------------------------------------------
# ChunkingService — edge cases
# ---------------------------------------------------------------------------


class TestChunkingServiceEdgeCases:
    def test_repeated_substrings_offsets_non_decreasing(self):
        """Documents with repeated paragraphs should still get correct offsets."""
        paragraph = "This is a repeated paragraph. " * 10
        text = paragraph + "\n\n" + paragraph + "\n\n" + paragraph
        svc = _make_service(chunk_size=100, chunk_overlap=20)
        result = svc.chunk_text(text, "doc-1")
        for i in range(1, len(result)):
            assert result[i].char_start >= result[i - 1].char_start

    def test_unknown_strategy_raises(self):
        """Pydantic rejects invalid strategy values at settings construction."""
        with pytest.raises(Exception, match="literal_error"):
            _make_settings(strategy="nonexistent")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Factory singleton
# ---------------------------------------------------------------------------


class TestFactory:
    def test_returns_same_instance(self):
        import app.chunking as chunking_mod

        chunking_mod._service = None
        try:
            svc1 = chunking_mod.get_chunking_service()
            svc2 = chunking_mod.get_chunking_service()
            assert svc1 is svc2
        finally:
            chunking_mod._service = None

    def test_uses_settings(self):
        import app.chunking as chunking_mod

        chunking_mod._service = None
        try:
            svc = chunking_mod.get_chunking_service()
            assert svc is not None
        finally:
            chunking_mod._service = None
