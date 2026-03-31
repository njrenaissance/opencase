"""Unit tests for the embedding module."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import EmbeddingSettings
from app.embedding.models import EmbeddingResult
from app.embedding.service import EmbeddingDimensionError, EmbeddingService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides: Any) -> EmbeddingSettings:
    defaults: dict[str, Any] = {
        "provider": "ollama",
        "model": "nomic-embed-text",
        "base_url": "http://ollama:11434",
        "dimensions": 768,
        "batch_size": 100,
        "request_timeout": 120,
    }
    defaults.update(overrides)
    return EmbeddingSettings(**defaults)


def _make_service(**overrides: Any) -> EmbeddingService:
    return EmbeddingService(_make_settings(**overrides))


def _make_chunk(
    document_id: str = "doc-1",
    chunk_index: int = 0,
    text: str = "hello world",
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "document_id": document_id,
        "chunk_index": chunk_index,
        "text": text,
        "char_start": 0,
        "char_end": len(text),
        "metadata": metadata or {},
    }


def _fake_vector(dimensions: int = 768) -> list[float]:
    return [0.1] * dimensions


def _mock_response(
    vectors: list[list[float]], status_code: int = 200
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json={"embeddings": vectors},
        request=httpx.Request("POST", "http://ollama:11434/api/embed"),
    )


# ---------------------------------------------------------------------------
# EmbeddingResult
# ---------------------------------------------------------------------------


class TestEmbeddingResult:
    def test_to_dict_all_fields(self):
        result = EmbeddingResult(
            document_id="doc-1",
            chunk_index=0,
            vector=[0.1, 0.2, 0.3],
            text="hello",
            metadata={"key": "value"},
        )
        d = result.to_dict()
        assert d["document_id"] == "doc-1"
        assert d["chunk_index"] == 0
        assert d["vector"] == [0.1, 0.2, 0.3]
        assert d["text"] == "hello"
        assert d["metadata"] == {"key": "value"}

    def test_to_dict_defaults(self):
        result = EmbeddingResult(
            document_id="doc-1",
            chunk_index=0,
            vector=[0.1],
            text="hi",
        )
        assert result.metadata == {}
        assert result.to_dict()["metadata"] == {}

    def test_frozen(self):
        result = EmbeddingResult(
            document_id="doc-1", chunk_index=0, vector=[0.1], text="hi"
        )
        with pytest.raises(AttributeError):
            result.text = "modified"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EmbeddingService — empty input
# ---------------------------------------------------------------------------


class TestEmbeddingServiceEmpty:
    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty(self):
        service = _make_service()
        results = await service.embed_chunks([])
        assert results == []


# ---------------------------------------------------------------------------
# EmbeddingService — successful embedding
# ---------------------------------------------------------------------------


class TestEmbeddingServiceSuccess:
    @pytest.mark.asyncio
    async def test_single_chunk(self):
        chunk = _make_chunk(text="test text")
        vector = _fake_vector()
        mock_resp = _mock_response([vector])

        service = _make_service()
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp
        ):
            results = await service.embed_chunks([chunk])

        assert len(results) == 1
        assert results[0].document_id == "doc-1"
        assert results[0].chunk_index == 0
        assert results[0].vector == vector
        assert results[0].text == "test text"

    @pytest.mark.asyncio
    async def test_multiple_chunks(self):
        chunks = [_make_chunk(chunk_index=i, text=f"text {i}") for i in range(5)]
        vectors = [_fake_vector() for _ in range(5)]
        mock_resp = _mock_response(vectors)

        service = _make_service()
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp
        ):
            results = await service.embed_chunks(chunks)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.chunk_index == i
            assert result.text == f"text {i}"

    @pytest.mark.asyncio
    async def test_metadata_passthrough(self):
        meta = {"firm_id": "f1", "matter_id": "m1", "source": "defense"}
        chunk = _make_chunk(metadata=meta)
        mock_resp = _mock_response([_fake_vector()])

        service = _make_service()
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp
        ):
            results = await service.embed_chunks([chunk])

        assert results[0].metadata == meta


# ---------------------------------------------------------------------------
# EmbeddingService — batching
# ---------------------------------------------------------------------------


class TestEmbeddingServiceBatching:
    @pytest.mark.asyncio
    async def test_batching_respects_batch_size(self):
        """10 chunks with batch_size=3 should produce 4 HTTP calls."""
        chunks = [_make_chunk(chunk_index=i, text=f"t{i}") for i in range(10)]
        service = _make_service(batch_size=3)

        call_count = 0
        batch_sizes: list[int] = []

        async def mock_post(url: str, **kwargs: Any) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            inputs = kwargs["json"]["input"]
            batch_sizes.append(len(inputs))
            vectors = [_fake_vector() for _ in inputs]
            return _mock_response(vectors)

        with patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
            results = await service.embed_chunks(chunks)

        assert call_count == 4
        assert batch_sizes == [3, 3, 3, 1]
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_single_batch_when_under_limit(self):
        """3 chunks with batch_size=100 should produce 1 HTTP call."""
        chunks = [_make_chunk(chunk_index=i) for i in range(3)]
        service = _make_service(batch_size=100)

        call_count = 0

        async def mock_post(url: str, **kwargs: Any) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            inputs = kwargs["json"]["input"]
            return _mock_response([_fake_vector() for _ in inputs])

        with patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
            results = await service.embed_chunks(chunks)

        assert call_count == 1
        assert len(results) == 3


# ---------------------------------------------------------------------------
# EmbeddingService — error handling
# ---------------------------------------------------------------------------


class TestEmbeddingServiceErrors:
    @pytest.mark.asyncio
    async def test_dimension_mismatch_raises(self):
        chunk = _make_chunk()
        wrong_vector = [0.1] * 512  # expected 768
        mock_resp = _mock_response([wrong_vector])

        service = _make_service(dimensions=768)
        with (
            patch.object(
                httpx.AsyncClient,
                "post",
                new_callable=AsyncMock,
                return_value=mock_resp,
            ),
            pytest.raises(EmbeddingDimensionError, match="Expected 768.*got 512"),
        ):
            await service.embed_chunks([chunk])

    @pytest.mark.asyncio
    async def test_vector_count_mismatch_raises(self):
        chunks = [_make_chunk(chunk_index=i) for i in range(3)]
        # Return only 2 vectors for 3 chunks
        mock_resp = _mock_response([_fake_vector(), _fake_vector()])

        service = _make_service()
        with (
            patch.object(
                httpx.AsyncClient,
                "post",
                new_callable=AsyncMock,
                return_value=mock_resp,
            ),
            pytest.raises(EmbeddingDimensionError, match="2 vectors.*3 inputs"),
        ):
            await service.embed_chunks(chunks)

    @pytest.mark.asyncio
    async def test_ollama_connection_error_raises(self):
        chunk = _make_chunk()
        service = _make_service()

        with (
            patch.object(
                httpx.AsyncClient,
                "post",
                new_callable=AsyncMock,
                side_effect=httpx.ConnectError("Connection refused"),
            ),
            pytest.raises(httpx.ConnectError),
        ):
            await service.embed_chunks([chunk])

    @pytest.mark.asyncio
    async def test_ollama_http_error_raises(self):
        chunk = _make_chunk()
        error_resp = httpx.Response(
            status_code=500,
            json={"error": "model not found"},
            request=httpx.Request("POST", "http://ollama:11434/api/embed"),
        )

        service = _make_service()
        with (
            patch.object(
                httpx.AsyncClient,
                "post",
                new_callable=AsyncMock,
                return_value=error_resp,
            ),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await service.embed_chunks([chunk])


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestFactory:
    def test_returns_same_instance(self):
        import app.embedding as mod

        mod._service = None
        s1 = mod.get_embedding_service()
        s2 = mod.get_embedding_service()
        assert s1 is s2
        mod._service = None  # cleanup

    def test_uses_settings(self):
        import app.embedding as mod

        mod._service = None
        service = mod.get_embedding_service()
        assert service._settings.model == "nomic-embed-text"
        mod._service = None  # cleanup
