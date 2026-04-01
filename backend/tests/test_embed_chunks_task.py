"""Unit tests for the embed_chunks Celery task."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from tests.factories import make_chunk, make_embedding_result, make_payload_metadata

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEmbedChunksTask:
    """Tests for the embed_chunks task (embed + upsert combined)."""

    @pytest.fixture(autouse=True)
    def _patch_services(self) -> Any:
        """Patch both embedding and vectorstore services."""
        self.mock_embedding_svc = AsyncMock()
        self.mock_vectorstore_svc = AsyncMock()

        with (
            patch(
                "app.embedding.get_embedding_service",
                return_value=self.mock_embedding_svc,
            ),
            patch(
                "app.vectorstore.get_vectorstore_service",
                return_value=self.mock_vectorstore_svc,
            ),
        ):
            yield

    def _run_task(
        self,
        document_id: str = "doc-1",
        chunks: list[dict[str, object]] | None = None,
        payload_metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        import asyncio

        from app.workers.tasks.embed_chunks import _embed

        return asyncio.run(
            _embed(
                document_id,
                chunks or [make_chunk()],
                payload_metadata or make_payload_metadata(),
            )
        )

    def test_calls_embedding_then_upsert(self) -> None:
        results = [make_embedding_result()]
        self.mock_embedding_svc.embed_chunks.return_value = results
        self.mock_vectorstore_svc.upsert_vectors.return_value = 1

        self._run_task()

        self.mock_embedding_svc.embed_chunks.assert_called_once()
        self.mock_vectorstore_svc.upsert_vectors.assert_called_once()
        # Verify upsert received the embedding results
        call_args = self.mock_vectorstore_svc.upsert_vectors.call_args
        assert call_args.args[0] is results

    def test_returns_summary_without_raw_vectors(self) -> None:
        self.mock_embedding_svc.embed_chunks.return_value = [make_embedding_result()]
        self.mock_vectorstore_svc.upsert_vectors.return_value = 1

        result = self._run_task()

        assert result["document_id"] == "doc-1"
        assert result["chunk_count"] == 1
        assert result["point_count"] == 1
        assert "embeddings" not in result
        assert "vector" not in result

    def test_embedding_error_prevents_upsert(self) -> None:
        self.mock_embedding_svc.embed_chunks.side_effect = RuntimeError("Ollama down")

        with pytest.raises(RuntimeError, match="Ollama down"):
            self._run_task()

        self.mock_vectorstore_svc.upsert_vectors.assert_not_called()

    def test_upsert_error_propagates(self) -> None:
        self.mock_embedding_svc.embed_chunks.return_value = [make_embedding_result()]
        self.mock_vectorstore_svc.upsert_vectors.side_effect = RuntimeError(
            "Qdrant down"
        )

        with pytest.raises(RuntimeError, match="Qdrant down"):
            self._run_task()

    def test_payload_metadata_passed_through(self) -> None:
        self.mock_embedding_svc.embed_chunks.return_value = [make_embedding_result()]
        self.mock_vectorstore_svc.upsert_vectors.return_value = 1
        meta = make_payload_metadata(bates_number="GOV-042", page_number=7)

        self._run_task(payload_metadata=meta)

        call_args = self.mock_vectorstore_svc.upsert_vectors.call_args
        assert call_args.args[1] is meta

    def test_multiple_chunks(self) -> None:
        chunks = [make_chunk(chunk_index=i) for i in range(5)]
        results = [make_embedding_result(chunk_index=i) for i in range(5)]
        self.mock_embedding_svc.embed_chunks.return_value = results
        self.mock_vectorstore_svc.upsert_vectors.return_value = 5

        result = self._run_task(chunks=chunks)

        assert result["chunk_count"] == 5
        assert result["point_count"] == 5
