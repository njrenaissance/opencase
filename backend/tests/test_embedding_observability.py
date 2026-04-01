"""Unit tests for embedding observability — spans and metrics.

Verifies that the embedding service emits the expected OpenTelemetry spans
and metrics.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.embedding.service import EmbeddingService
from tests.factories import make_chunk, make_embedding_settings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DIMS = 4  # small dimension for tests


@pytest.fixture
def otel_spans():
    """Provide a TracerProvider + InMemorySpanExporter for span assertions."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


@pytest.fixture
def mock_metrics():
    """Return mock metric instruments to patch into embedding service."""
    return {
        "embedding_completed": MagicMock(),
        "embedding_failed": MagicMock(),
        "embedding_duration_seconds": MagicMock(),
        "embedding_chunks_processed": MagicMock(),
        "embedding_batch_count": MagicMock(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_chunks(n: int) -> list[dict]:
    return [make_chunk(chunk_index=i, text=f"chunk {i}") for i in range(n)]


def _mock_transport(
    dims: int = _DIMS,
    num_vectors: int | None = None,
    status: int = 200,
) -> httpx.MockTransport:
    """Return a transport that responds to /api/embed with fake vectors."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed" and request.method == "POST":
            if status != 200:
                return httpx.Response(status, request=request)
            import json

            body = request.content
            data = json.loads(body)
            count = num_vectors if num_vectors is not None else len(data["input"])
            vectors = [[0.1] * dims for _ in range(count)]
            return httpx.Response(
                200,
                json={"embeddings": vectors},
                request=request,
            )
        return httpx.Response(404, request=request)

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Span tests
# ---------------------------------------------------------------------------


class TestEmbeddingSpans:
    async def _run(self, otel_spans, chunks=None, transport=None):
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        chunks = chunks if chunks is not None else _sample_chunks(3)
        transport = transport or _mock_transport()
        svc = EmbeddingService(
            make_embedding_settings(dimensions=_DIMS, batch_size=2, request_timeout=10)
        )

        with (
            patch("app.embedding.service.tracer", test_tracer),
            patch(
                "app.embedding.service.httpx.AsyncClient",
                _make_patched_client_cls(transport),
            ),
        ):
            result = await svc.embed_chunks(chunks)

        return exporter.get_finished_spans(), result

    @pytest.mark.asyncio
    async def test_creates_span(self, otel_spans):
        spans, _ = await self._run(otel_spans)
        matching = [s for s in spans if s.name == "embedding.embed_chunks"]
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_span_has_input_attributes(self, otel_spans):
        chunks = _sample_chunks(3)
        spans, _ = await self._run(otel_spans, chunks=chunks)
        span = [s for s in spans if s.name == "embedding.embed_chunks"][0]
        assert span.attributes["embedding.chunk_count"] == 3
        assert span.attributes["embedding.model"] == "nomic-embed-text"
        assert span.attributes["embedding.batch_size"] == 2

    @pytest.mark.asyncio
    async def test_span_has_result_attributes(self, otel_spans):
        chunks = _sample_chunks(3)
        spans, results = await self._run(otel_spans, chunks=chunks)
        span = [s for s in spans if s.name == "embedding.embed_chunks"][0]
        assert span.attributes["embedding.result_count"] == 3
        assert span.attributes["embedding.batch_count"] == 2  # ceil(3/2)

    @pytest.mark.asyncio
    async def test_records_error_on_failure(self, otel_spans):
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        transport = _mock_transport(status=500)
        svc = EmbeddingService(
            make_embedding_settings(dimensions=_DIMS, batch_size=2, request_timeout=10)
        )

        with (
            patch("app.embedding.service.tracer", test_tracer),
            patch(
                "app.embedding.service.httpx.AsyncClient",
                _make_patched_client_cls(transport),
            ),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await svc.embed_chunks(_sample_chunks(1))

        spans = exporter.get_finished_spans()
        span = [s for s in spans if s.name == "embedding.embed_chunks"][0]
        assert span.status.status_code.name == "ERROR"
        events = [e for e in span.events if e.name == "exception"]
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_no_span_for_empty_chunks(self, otel_spans):
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        svc = EmbeddingService(
            make_embedding_settings(dimensions=_DIMS, batch_size=2, request_timeout=10)
        )
        with patch("app.embedding.service.tracer", test_tracer):
            result = await svc.embed_chunks([])

        assert result == []
        assert len(exporter.get_finished_spans()) == 0


# ---------------------------------------------------------------------------
# Metric tests
# ---------------------------------------------------------------------------


def _make_patched_client_cls(transport: httpx.MockTransport) -> type:
    """Create an httpx.AsyncClient subclass that injects the mock transport."""

    class PatchedClient(httpx.AsyncClient):
        def __init__(self, **kwargs):  # noqa: ANN003
            kwargs["transport"] = transport
            super().__init__(**kwargs)

    return PatchedClient


class TestEmbeddingMetrics:
    @pytest.mark.asyncio
    async def test_completed_counter_increments(self, mock_metrics):
        transport = _mock_transport()
        svc = EmbeddingService(
            make_embedding_settings(dimensions=_DIMS, batch_size=2, request_timeout=10)
        )

        with (
            patch.multiple("app.embedding.service", **mock_metrics),
            patch(
                "app.embedding.service.httpx.AsyncClient",
                _make_patched_client_cls(transport),
            ),
        ):
            await svc.embed_chunks(_sample_chunks(2))

        mock_metrics["embedding_completed"].add.assert_called_once()
        args, _ = mock_metrics["embedding_completed"].add.call_args
        assert args[0] == 1
        assert args[1]["model"] == "nomic-embed-text"

    @pytest.mark.asyncio
    async def test_failed_counter_on_error(self, mock_metrics):
        transport = _mock_transport(status=500)
        svc = EmbeddingService(
            make_embedding_settings(dimensions=_DIMS, batch_size=2, request_timeout=10)
        )

        with (
            patch.multiple("app.embedding.service", **mock_metrics),
            patch(
                "app.embedding.service.httpx.AsyncClient",
                _make_patched_client_cls(transport),
            ),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await svc.embed_chunks(_sample_chunks(1))

        mock_metrics["embedding_failed"].add.assert_called_once()
        args, _ = mock_metrics["embedding_failed"].add.call_args
        assert args[0] == 1
        assert args[1]["model"] == "nomic-embed-text"
        assert args[1]["error_type"] == "HTTPStatusError"

    @pytest.mark.asyncio
    async def test_duration_recorded(self, mock_metrics):
        transport = _mock_transport()
        svc = EmbeddingService(
            make_embedding_settings(dimensions=_DIMS, batch_size=2, request_timeout=10)
        )

        with (
            patch.multiple("app.embedding.service", **mock_metrics),
            patch(
                "app.embedding.service.httpx.AsyncClient",
                _make_patched_client_cls(transport),
            ),
        ):
            await svc.embed_chunks(_sample_chunks(1))

        mock_metrics["embedding_duration_seconds"].record.assert_called_once()
        args, _ = mock_metrics["embedding_duration_seconds"].record.call_args
        assert args[0] >= 0

    @pytest.mark.asyncio
    async def test_duration_recorded_on_failure(self, mock_metrics):
        transport = _mock_transport(status=500)
        svc = EmbeddingService(
            make_embedding_settings(dimensions=_DIMS, batch_size=2, request_timeout=10)
        )

        with (
            patch.multiple("app.embedding.service", **mock_metrics),
            patch(
                "app.embedding.service.httpx.AsyncClient",
                _make_patched_client_cls(transport),
            ),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await svc.embed_chunks(_sample_chunks(1))

        mock_metrics["embedding_duration_seconds"].record.assert_called_once()

    @pytest.mark.asyncio
    async def test_chunks_processed_recorded(self, mock_metrics):
        transport = _mock_transport()
        svc = EmbeddingService(
            make_embedding_settings(dimensions=_DIMS, batch_size=2, request_timeout=10)
        )

        with (
            patch.multiple("app.embedding.service", **mock_metrics),
            patch(
                "app.embedding.service.httpx.AsyncClient",
                _make_patched_client_cls(transport),
            ),
        ):
            await svc.embed_chunks(_sample_chunks(3))

        mock_metrics["embedding_chunks_processed"].record.assert_called_once()
        args, _ = mock_metrics["embedding_chunks_processed"].record.call_args
        assert args[0] == 3

    @pytest.mark.asyncio
    async def test_batch_count_recorded(self, mock_metrics):
        transport = _mock_transport()
        svc = EmbeddingService(
            make_embedding_settings(dimensions=_DIMS, batch_size=2, request_timeout=10)
        )  # batch_size=2

        with (
            patch.multiple("app.embedding.service", **mock_metrics),
            patch(
                "app.embedding.service.httpx.AsyncClient",
                _make_patched_client_cls(transport),
            ),
        ):
            await svc.embed_chunks(_sample_chunks(3))

        mock_metrics["embedding_batch_count"].record.assert_called_once()
        args, _ = mock_metrics["embedding_batch_count"].record.call_args
        assert args[0] == 2  # ceil(3/2)
