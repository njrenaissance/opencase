"""Integration tests for EmbeddingService against a live Ollama container.

Requires the Docker stack to be running (``pytest -m integration``).
"""

from __future__ import annotations

import pytest

from app.embedding.service import EmbeddingService
from tests.factories import make_chunk, make_embedding_settings


def _make_service(host: str, port: int) -> EmbeddingService:
    return EmbeddingService(
        make_embedding_settings(base_url=f"http://{host}:{port}", batch_size=10)
    )


@pytest.mark.integration
class TestOllamaEmbeddingLive:
    @pytest.mark.asyncio
    async def test_embed_single_chunk(self, ollama_service):
        host, port = ollama_service
        service = _make_service(host, port)
        chunk = make_chunk(
            text="Criminal defense discovery obligations under CPL 245",
            document_id="test-doc",
            metadata={"source": "integration_test"},
        )

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
            make_chunk(
                text="Brady material disclosure requirements",
                chunk_index=0,
                document_id="test-doc",
            ),
            make_chunk(
                text="Giglio witness impeachment evidence",
                chunk_index=1,
                document_id="test-doc",
            ),
            make_chunk(
                text="Jencks Act prior statements of witnesses",
                chunk_index=2,
                document_id="test-doc",
            ),
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
        chunk = make_chunk(
            text="Speedy trial clock under CPL 30.30",
            document_id="test-doc",
        )

        results1 = await service.embed_chunks([chunk])
        results2 = await service.embed_chunks([chunk])

        assert len(results1[0].vector) == len(results2[0].vector) == 768

    @pytest.mark.asyncio
    async def test_metadata_passthrough(self, ollama_service):
        host, port = ollama_service
        service = _make_service(host, port)
        chunk = make_chunk(
            text="Test metadata passthrough",
            document_id="test-doc",
            metadata={"source": "integration_test"},
        )

        results = await service.embed_chunks([chunk])

        assert results[0].metadata == {"source": "integration_test"}

    @pytest.mark.asyncio
    async def test_empty_input(self, ollama_service):
        host, port = ollama_service
        service = _make_service(host, port)

        results = await service.embed_chunks([])

        assert results == []
