"""Integration tests for EmbeddingService against a live Ollama container.

Requires the Docker stack to be running (``pytest -m integration``).
"""

from __future__ import annotations

import pytest

from app.core.config import EmbeddingSettings
from app.embedding.service import EmbeddingService


def _make_service(host: str, port: int) -> EmbeddingService:
    settings = EmbeddingSettings(
        provider="ollama",
        model="nomic-embed-text",
        base_url=f"http://{host}:{port}",
        dimensions=768,
        batch_size=10,
        request_timeout=120,
    )
    return EmbeddingService(settings)


def _make_chunk(
    text: str, chunk_index: int = 0, document_id: str = "test-doc"
) -> dict[str, object]:
    return {
        "document_id": document_id,
        "chunk_index": chunk_index,
        "text": text,
        "char_start": 0,
        "char_end": len(text),
        "metadata": {"source": "integration_test"},
    }


@pytest.mark.integration
class TestOllamaEmbeddingLive:
    @pytest.mark.asyncio
    async def test_embed_single_chunk(self, ollama_service):
        host, port = ollama_service
        service = _make_service(host, port)
        chunk = _make_chunk("Criminal defense discovery obligations under CPL 245")

        results = await service.embed_chunks([chunk])

        assert len(results) == 1
        assert len(results[0].vector) == 768
        assert results[0].document_id == "test-doc"
        assert results[0].chunk_index == 0
        assert all(isinstance(v, float) for v in results[0].vector)

    @pytest.mark.asyncio
    async def test_embed_multiple_chunks(self, ollama_service):
        host, port = ollama_service
        service = _make_service(host, port)
        chunks = [
            _make_chunk("Brady material disclosure requirements", chunk_index=0),
            _make_chunk("Giglio witness impeachment evidence", chunk_index=1),
            _make_chunk("Jencks Act prior statements of witnesses", chunk_index=2),
        ]

        results = await service.embed_chunks(chunks)

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.chunk_index == i
            assert len(result.vector) == 768

    @pytest.mark.asyncio
    async def test_same_input_same_dimensions(self, ollama_service):
        """Verify deterministic output shape for identical input."""
        host, port = ollama_service
        service = _make_service(host, port)
        chunk = _make_chunk("Speedy trial clock under CPL 30.30")

        results1 = await service.embed_chunks([chunk])
        results2 = await service.embed_chunks([chunk])

        assert len(results1[0].vector) == len(results2[0].vector) == 768

    @pytest.mark.asyncio
    async def test_metadata_passthrough(self, ollama_service):
        host, port = ollama_service
        service = _make_service(host, port)
        chunk = _make_chunk("Test metadata passthrough")

        results = await service.embed_chunks([chunk])

        assert results[0].metadata == {"source": "integration_test"}

    @pytest.mark.asyncio
    async def test_empty_input(self, ollama_service):
        host, port = ollama_service
        service = _make_service(host, port)

        results = await service.embed_chunks([])

        assert results == []
