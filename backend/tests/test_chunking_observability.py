"""Unit tests for chunking observability — spans and metrics.

Verifies that the chunking service emits the expected OpenTelemetry spans
and metrics.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.chunking.service import ChunkingService
from tests.factories import make_chunking_settings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def otel_spans():
    """Provide a TracerProvider + InMemorySpanExporter for span assertions."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


@pytest.fixture
def mock_metrics():
    """Return mock metric instruments to patch into chunking service."""
    return {
        "chunking_completed": MagicMock(),
        "chunking_failed": MagicMock(),
        "chunking_duration_seconds": MagicMock(),
        "chunking_text_length_chars": MagicMock(),
        "chunking_chunks_produced": MagicMock(),
    }


# ---------------------------------------------------------------------------
# Span tests
# ---------------------------------------------------------------------------


class TestChunkingSpans:
    def _run(self, otel_spans, text="Hello world. This is a test document.", **kwargs):
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        svc = ChunkingService(make_chunking_settings())
        with patch("app.chunking.service.tracer", test_tracer):
            result = svc.chunk_text(text, "doc-1", **kwargs)

        return exporter.get_finished_spans(), result

    def test_creates_span(self, otel_spans):
        spans, _ = self._run(otel_spans)
        matching = [s for s in spans if s.name == "chunking.chunk_text"]
        assert len(matching) == 1

    def test_span_has_input_attributes(self, otel_spans):
        text = "Hello world. This is a test document."
        spans, _ = self._run(otel_spans, text=text)
        span = [s for s in spans if s.name == "chunking.chunk_text"][0]
        assert span.attributes["chunking.document_id"] == "doc-1"
        assert span.attributes["chunking.text_length"] == len(text)

    def test_span_has_result_attributes(self, otel_spans):
        spans, results = self._run(otel_spans)
        span = [s for s in spans if s.name == "chunking.chunk_text"][0]
        assert span.attributes["chunking.chunk_count"] == len(results)
        assert span.attributes["chunking.strategy"] == "RecursiveStrategy"

    def test_records_error_on_failure(self, otel_spans):
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        svc = ChunkingService(make_chunking_settings())
        with (
            patch("app.chunking.service.tracer", test_tracer),
            patch.object(svc._strategy, "split", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError, match="boom"),
        ):
            svc.chunk_text("some text", "doc-1")

        spans = exporter.get_finished_spans()
        span = [s for s in spans if s.name == "chunking.chunk_text"][0]
        assert span.status.status_code.name == "ERROR"
        events = [e for e in span.events if e.name == "exception"]
        assert len(events) >= 1

    def test_no_span_for_empty_text(self, otel_spans):
        spans, results = self._run(otel_spans, text="")
        assert results == []
        assert len(spans) == 0

    def test_no_span_for_whitespace_text(self, otel_spans):
        spans, results = self._run(otel_spans, text="   \n  ")
        assert results == []
        assert len(spans) == 0


# ---------------------------------------------------------------------------
# Metric tests
# ---------------------------------------------------------------------------


class TestChunkingMetrics:
    def test_completed_counter_increments(self, mock_metrics):
        svc = ChunkingService(make_chunking_settings())
        with patch.multiple("app.chunking.service", **mock_metrics):
            svc.chunk_text("Hello world. This is a test.", "doc-1")

        mock_metrics["chunking_completed"].add.assert_called_once()
        args, _ = mock_metrics["chunking_completed"].add.call_args
        assert args[0] == 1
        assert args[1]["strategy"] == "RecursiveStrategy"

    def test_failed_counter_on_error(self, mock_metrics):
        svc = ChunkingService(make_chunking_settings())
        with (
            patch.multiple("app.chunking.service", **mock_metrics),
            patch.object(svc._strategy, "split", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError),
        ):
            svc.chunk_text("some text", "doc-1")

        mock_metrics["chunking_failed"].add.assert_called_once()
        args, _ = mock_metrics["chunking_failed"].add.call_args
        assert args[0] == 1
        assert args[1]["error_type"] == "RuntimeError"

    def test_duration_recorded(self, mock_metrics):
        svc = ChunkingService(make_chunking_settings())
        with patch.multiple("app.chunking.service", **mock_metrics):
            svc.chunk_text("Hello world.", "doc-1")

        mock_metrics["chunking_duration_seconds"].record.assert_called_once()
        args, _ = mock_metrics["chunking_duration_seconds"].record.call_args
        assert args[0] >= 0

    def test_duration_recorded_on_failure(self, mock_metrics):
        svc = ChunkingService(make_chunking_settings())
        with (
            patch.multiple("app.chunking.service", **mock_metrics),
            patch.object(svc._strategy, "split", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError),
        ):
            svc.chunk_text("some text", "doc-1")

        mock_metrics["chunking_duration_seconds"].record.assert_called_once()

    def test_text_length_recorded(self, mock_metrics):
        text = "Hello world. This is a test."
        svc = ChunkingService(make_chunking_settings())
        with patch.multiple("app.chunking.service", **mock_metrics):
            svc.chunk_text(text, "doc-1")

        mock_metrics["chunking_text_length_chars"].record.assert_called_once()
        args, _ = mock_metrics["chunking_text_length_chars"].record.call_args
        assert args[0] == len(text)

    def test_chunks_produced_recorded(self, mock_metrics):
        svc = ChunkingService(make_chunking_settings())
        with patch.multiple("app.chunking.service", **mock_metrics):
            results = svc.chunk_text("Hello world. This is a test.", "doc-1")

        mock_metrics["chunking_chunks_produced"].record.assert_called_once()
        args, _ = mock_metrics["chunking_chunks_produced"].record.call_args
        assert args[0] == len(results)
