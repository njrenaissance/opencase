"""Unit tests for vectorstore observability — spans and metrics.

Verifies that the Qdrant vector store service emits the expected
OpenTelemetry spans and metrics.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.vectorstore.service import QdrantVectorStore
from tests.factories import (
    make_embedding_result,
    make_embedding_settings,
    make_payload_metadata,
    make_qdrant_settings,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DIMS = 4
_COLLECTION = "test_collection"


@pytest.fixture
def otel_spans():
    """Provide a TracerProvider + InMemorySpanExporter for span assertions."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


@pytest.fixture
def mock_metrics():
    """Return mock metric instruments to patch into vectorstore service."""
    return {
        "vectorstore_upsert_completed": MagicMock(),
        "vectorstore_upsert_failed": MagicMock(),
        "vectorstore_upsert_duration_seconds": MagicMock(),
        "vectorstore_upsert_points": MagicMock(),
        "vectorstore_delete_completed": MagicMock(),
        "vectorstore_delete_duration_seconds": MagicMock(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(mock_client: AsyncMock | None = None) -> QdrantVectorStore:
    qdrant_settings = make_qdrant_settings(collection=_COLLECTION)
    embedding_settings = make_embedding_settings(dimensions=_DIMS)
    with patch(
        "app.vectorstore.service.AsyncQdrantClient",
        return_value=mock_client or AsyncMock(),
    ):
        svc = QdrantVectorStore(qdrant_settings, embedding_settings)
    if mock_client is not None:
        svc._client = mock_client
    return svc


def _sample_embeddings(n: int) -> list:
    return [
        make_embedding_result(chunk_index=i, text=f"chunk {i}", dimensions=_DIMS)
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Upsert span tests
# ---------------------------------------------------------------------------


class TestVectorstoreUpsertSpans:
    @pytest.mark.asyncio
    async def test_creates_span(self, otel_spans):
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        mock_client = AsyncMock()
        svc = _make_service(mock_client)

        with patch("app.vectorstore.service.tracer", test_tracer):
            await svc.upsert_vectors(_sample_embeddings(2), make_payload_metadata())

        spans = exporter.get_finished_spans()
        matching = [s for s in spans if s.name == "vectorstore.upsert_vectors"]
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_span_has_attributes(self, otel_spans):
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        mock_client = AsyncMock()
        svc = _make_service(mock_client)

        with patch("app.vectorstore.service.tracer", test_tracer):
            await svc.upsert_vectors(_sample_embeddings(3), make_payload_metadata())

        spans = exporter.get_finished_spans()
        span = [s for s in spans if s.name == "vectorstore.upsert_vectors"][0]
        assert span.attributes["vectorstore.collection"] == "test_collection"
        assert span.attributes["vectorstore.point_count"] == 3
        assert span.attributes["vectorstore.batch_count"] == 1

    @pytest.mark.asyncio
    async def test_records_error_on_failure(self, otel_spans):
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        mock_client = AsyncMock()
        mock_client.upsert.side_effect = RuntimeError("Qdrant down")
        svc = _make_service(mock_client)

        with (
            patch("app.vectorstore.service.tracer", test_tracer),
            pytest.raises(RuntimeError, match="Qdrant down"),
        ):
            await svc.upsert_vectors(_sample_embeddings(1), make_payload_metadata())

        spans = exporter.get_finished_spans()
        span = [s for s in spans if s.name == "vectorstore.upsert_vectors"][0]
        assert span.status.status_code.name == "ERROR"
        events = [e for e in span.events if e.name == "exception"]
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_no_span_for_empty_embeddings(self, otel_spans):
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        mock_client = AsyncMock()
        svc = _make_service(mock_client)

        with patch("app.vectorstore.service.tracer", test_tracer):
            result = await svc.upsert_vectors([], make_payload_metadata())

        assert result == 0
        assert len(exporter.get_finished_spans()) == 0


# ---------------------------------------------------------------------------
# Delete span tests
# ---------------------------------------------------------------------------


class TestVectorstoreDeleteSpans:
    @pytest.mark.asyncio
    async def test_creates_span(self, otel_spans):
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        mock_client = AsyncMock()
        mock_client.scroll.return_value = ([], None)
        svc = _make_service(mock_client)

        with patch("app.vectorstore.service.tracer", test_tracer):
            await svc.delete_by_document("doc-1")

        spans = exporter.get_finished_spans()
        matching = [s for s in spans if s.name == "vectorstore.delete_by_document"]
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_span_has_attributes(self, otel_spans):
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        mock_client = AsyncMock()
        mock_client.scroll.return_value = ([MagicMock(), MagicMock()], None)
        svc = _make_service(mock_client)

        with patch("app.vectorstore.service.tracer", test_tracer):
            await svc.delete_by_document("doc-1")

        spans = exporter.get_finished_spans()
        span = [s for s in spans if s.name == "vectorstore.delete_by_document"][0]
        assert span.attributes["vectorstore.collection"] == "test_collection"
        assert span.attributes["vectorstore.document_id"] == "doc-1"
        assert span.attributes["vectorstore.deleted_count"] == 2

    @pytest.mark.asyncio
    async def test_records_error_on_failure(self, otel_spans):
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        mock_client = AsyncMock()
        mock_client.scroll.side_effect = RuntimeError("Qdrant down")
        svc = _make_service(mock_client)

        with (
            patch("app.vectorstore.service.tracer", test_tracer),
            pytest.raises(RuntimeError, match="Qdrant down"),
        ):
            await svc.delete_by_document("doc-1")

        spans = exporter.get_finished_spans()
        span = [s for s in spans if s.name == "vectorstore.delete_by_document"][0]
        assert span.status.status_code.name == "ERROR"
        events = [e for e in span.events if e.name == "exception"]
        assert len(events) >= 1


# ---------------------------------------------------------------------------
# Metric tests
# ---------------------------------------------------------------------------


class TestVectorstoreMetrics:
    @pytest.mark.asyncio
    async def test_upsert_completed_counter(self, mock_metrics):
        mock_client = AsyncMock()
        svc = _make_service(mock_client)

        with patch.multiple("app.vectorstore.service", **mock_metrics):
            await svc.upsert_vectors(_sample_embeddings(2), make_payload_metadata())

        mock_metrics["vectorstore_upsert_completed"].add.assert_called_once()
        args, _ = mock_metrics["vectorstore_upsert_completed"].add.call_args
        assert args[0] == 1
        assert args[1]["collection"] == "test_collection"

    @pytest.mark.asyncio
    async def test_upsert_failed_counter(self, mock_metrics):
        mock_client = AsyncMock()
        mock_client.upsert.side_effect = RuntimeError("Qdrant down")
        svc = _make_service(mock_client)

        with (
            patch.multiple("app.vectorstore.service", **mock_metrics),
            pytest.raises(RuntimeError),
        ):
            await svc.upsert_vectors(_sample_embeddings(1), make_payload_metadata())

        mock_metrics["vectorstore_upsert_failed"].add.assert_called_once()
        args, _ = mock_metrics["vectorstore_upsert_failed"].add.call_args
        assert args[0] == 1
        assert args[1]["collection"] == "test_collection"
        assert args[1]["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_upsert_duration_recorded(self, mock_metrics):
        mock_client = AsyncMock()
        svc = _make_service(mock_client)

        with patch.multiple("app.vectorstore.service", **mock_metrics):
            await svc.upsert_vectors(_sample_embeddings(1), make_payload_metadata())

        mock_metrics["vectorstore_upsert_duration_seconds"].record.assert_called_once()
        args, _ = mock_metrics["vectorstore_upsert_duration_seconds"].record.call_args
        assert args[0] >= 0

    @pytest.mark.asyncio
    async def test_upsert_duration_recorded_on_failure(self, mock_metrics):
        mock_client = AsyncMock()
        mock_client.upsert.side_effect = RuntimeError("Qdrant down")
        svc = _make_service(mock_client)

        with (
            patch.multiple("app.vectorstore.service", **mock_metrics),
            pytest.raises(RuntimeError),
        ):
            await svc.upsert_vectors(_sample_embeddings(1), make_payload_metadata())

        mock_metrics["vectorstore_upsert_duration_seconds"].record.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_points_recorded(self, mock_metrics):
        mock_client = AsyncMock()
        svc = _make_service(mock_client)

        with patch.multiple("app.vectorstore.service", **mock_metrics):
            await svc.upsert_vectors(_sample_embeddings(3), make_payload_metadata())

        mock_metrics["vectorstore_upsert_points"].record.assert_called_once()
        args, _ = mock_metrics["vectorstore_upsert_points"].record.call_args
        assert args[0] == 3

    @pytest.mark.asyncio
    async def test_delete_completed_counter(self, mock_metrics):
        mock_client = AsyncMock()
        mock_client.scroll.return_value = ([MagicMock()], None)
        svc = _make_service(mock_client)

        with patch.multiple("app.vectorstore.service", **mock_metrics):
            await svc.delete_by_document("doc-1")

        mock_metrics["vectorstore_delete_completed"].add.assert_called_once()
        args, _ = mock_metrics["vectorstore_delete_completed"].add.call_args
        assert args[0] == 1
        assert args[1]["collection"] == "test_collection"

    @pytest.mark.asyncio
    async def test_delete_duration_recorded(self, mock_metrics):
        mock_client = AsyncMock()
        mock_client.scroll.return_value = ([], None)
        svc = _make_service(mock_client)

        with patch.multiple("app.vectorstore.service", **mock_metrics):
            await svc.delete_by_document("doc-1")

        mock_metrics["vectorstore_delete_duration_seconds"].record.assert_called_once()
        args, _ = mock_metrics["vectorstore_delete_duration_seconds"].record.call_args
        assert args[0] >= 0
