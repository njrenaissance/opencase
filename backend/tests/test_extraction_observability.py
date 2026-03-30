"""Unit tests for extraction observability — spans and metrics.

Verifies that the extraction service and Celery tasks emit the expected
OpenTelemetry spans and metrics.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core.config import ExtractionSettings
from app.extraction.models import ExtractionResult
from app.extraction.tika import TikaExtractionService

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
    """Return mock metric instruments to patch into tika.py."""
    return {
        "extraction_completed": MagicMock(),
        "extraction_failed": MagicMock(),
        "extraction_duration_seconds": MagicMock(),
        "extraction_document_size_bytes": MagicMock(),
        "extraction_text_length_chars": MagicMock(),
    }


# ---------------------------------------------------------------------------
# Helpers — Tika mock (same pattern as test_extraction.py)
# ---------------------------------------------------------------------------


def _make_settings(**overrides) -> ExtractionSettings:
    defaults = {
        "tika_url": "http://tika:9998",
        "ocr_enabled": True,
        "ocr_languages": "eng",
        "request_timeout": 10,
        "max_file_size_bytes": 1024,
    }
    defaults.update(overrides)
    return ExtractionSettings(**defaults)


def _mock_transport(
    text_body: str = "extracted text",
    meta_body: dict | None = None,
    status: int = 200,
) -> httpx.MockTransport:
    if meta_body is None:
        meta_body = {"Content-Type": "text/plain", "language": "en"}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rmeta/text" and request.method == "PUT":
            payload = dict(meta_body)
            payload.setdefault("X-TIKA:content", text_body)
            return httpx.Response(status, json=[payload], request=request)
        return httpx.Response(404, request=request)

    return httpx.MockTransport(handler)


def _make_service(
    settings: ExtractionSettings | None = None,
    transport: httpx.MockTransport | None = None,
) -> TikaExtractionService:
    s = settings or _make_settings()
    svc = TikaExtractionService(s)
    if transport is not None:

        def _patched_client() -> httpx.AsyncClient:
            return httpx.AsyncClient(transport=transport, base_url=s.tika_url)

        svc._make_client = _patched_client  # type: ignore[method-assign]
    return svc


# ---------------------------------------------------------------------------
# Helpers — mock S3 + extraction (same pattern as test_workers.py)
# ---------------------------------------------------------------------------


def _mock_result(**overrides) -> ExtractionResult:
    defaults = {
        "text": "hello",
        "content_type": "text/plain",
        "metadata": {},
        "ocr_applied": False,
        "language": "en",
    }
    defaults.update(overrides)
    return ExtractionResult(**defaults)


# ---------------------------------------------------------------------------
# Span tests — extract_document task
# ---------------------------------------------------------------------------


class TestExtractDocumentSpans:
    def _run_task(self, otel_spans, mock_result_obj=None, storage_side_effect=None):
        """Run extract_document with a test tracer patched in."""
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        result = mock_result_obj or _mock_result()
        mock_storage = AsyncMock()
        if storage_side_effect:
            mock_storage.download_document.side_effect = storage_side_effect
        else:
            mock_storage.download_document.return_value = (b"data", "text/plain")
        mock_extraction = AsyncMock()
        mock_extraction.extract_text.return_value = result

        with (
            patch("app.storage.get_storage_service", return_value=mock_storage),
            patch(
                "app.extraction.get_extraction_service",
                return_value=mock_extraction,
            ),
            patch("app.workers.tasks.extract_document.tracer", test_tracer),
        ):
            from app.workers.tasks.extract_document import extract_document

            extract_document("doc-1", "firm/matter/doc/original.pdf")

        return exporter.get_finished_spans()

    def test_creates_parent_span(self, otel_spans):
        spans = self._run_task(otel_spans)
        parent = [s for s in spans if s.name == "extract_document"]
        assert len(parent) == 1
        assert parent[0].attributes["document.id"] == "doc-1"
        assert parent[0].attributes["document.s3_key"] == "firm/matter/doc/original.pdf"

    def test_creates_s3_download_child_span(self, otel_spans):
        spans = self._run_task(otel_spans)
        download_spans = [s for s in spans if s.name == "extraction.s3_download"]
        assert len(download_spans) == 1

        parent = [s for s in spans if s.name == "extract_document"][0]
        assert download_spans[0].parent.span_id == parent.context.span_id

    def test_sets_result_attributes(self, otel_spans):
        spans = self._run_task(otel_spans)
        parent = [s for s in spans if s.name == "extract_document"][0]
        assert parent.attributes["extraction.text_length"] == 5
        assert parent.attributes["extraction.ocr_applied"] is False

    def test_records_error_on_failure(self, otel_spans):
        with pytest.raises(RuntimeError, match="S3 down"):
            self._run_task(otel_spans, storage_side_effect=RuntimeError("S3 down"))

        _, exporter = otel_spans
        spans = exporter.get_finished_spans()
        parent = [s for s in spans if s.name == "extract_document"][0]
        assert parent.status.status_code.name == "ERROR"
        events = [e for e in parent.events if e.name == "exception"]
        assert len(events) >= 1


# ---------------------------------------------------------------------------
# Span tests — ingest_document task
# ---------------------------------------------------------------------------


class TestIngestDocumentSpans:
    def _run_task(self, otel_spans, upload_side_effect=None):
        """Run ingest_document with a test tracer patched in."""
        provider, exporter = otel_spans
        test_tracer = provider.get_tracer("test")

        result = _mock_result()
        mock_storage = AsyncMock()
        mock_storage.download_document.return_value = (b"data", "text/plain")
        if upload_side_effect:
            mock_storage.upload_json.side_effect = upload_side_effect
        mock_extraction = AsyncMock()
        mock_extraction.extract_text.return_value = result

        with (
            patch("app.storage.get_storage_service", return_value=mock_storage),
            patch(
                "app.extraction.get_extraction_service",
                return_value=mock_extraction,
            ),
            patch("app.workers.tasks.ingest_document.tracer", test_tracer),
        ):
            from app.workers.tasks.ingest_document import ingest_document

            ingest_document("doc-1", "firm/matter/doc/original.pdf")

        return exporter.get_finished_spans()

    def test_creates_parent_span(self, otel_spans):
        spans = self._run_task(otel_spans)
        parent = [s for s in spans if s.name == "ingest_document"]
        assert len(parent) == 1
        assert parent[0].attributes["document.id"] == "doc-1"

    def test_creates_upload_child_span(self, otel_spans):
        spans = self._run_task(otel_spans)
        upload_spans = [s for s in spans if s.name == "ingestion.s3_upload"]
        assert len(upload_spans) == 1

        parent = [s for s in spans if s.name == "ingest_document"][0]
        assert upload_spans[0].parent.span_id == parent.context.span_id

    def test_creates_download_child_span(self, otel_spans):
        spans = self._run_task(otel_spans)
        download_spans = [s for s in spans if s.name == "ingestion.s3_download"]
        assert len(download_spans) == 1

    def test_sets_result_attributes(self, otel_spans):
        spans = self._run_task(otel_spans)
        parent = [s for s in spans if s.name == "ingest_document"][0]
        assert parent.attributes["extraction.text_length"] == 5
        expected_key = "firm/matter/doc/extracted.json"
        assert parent.attributes["ingestion.extracted_key"] == expected_key

    def test_records_error_on_failure(self, otel_spans):
        with pytest.raises(RuntimeError, match="S3 upload failed"):
            self._run_task(
                otel_spans,
                upload_side_effect=RuntimeError("S3 upload failed"),
            )

        _, exporter = otel_spans
        spans = exporter.get_finished_spans()
        parent = [s for s in spans if s.name == "ingest_document"][0]
        assert parent.status.status_code.name == "ERROR"
        events = [e for e in parent.events if e.name == "exception"]
        assert len(events) >= 1


# ---------------------------------------------------------------------------
# Metric tests — TikaExtractionService
# ---------------------------------------------------------------------------


class TestExtractionMetrics:
    @pytest.mark.asyncio
    async def test_completed_counter_increments(self, mock_metrics):
        transport = _mock_transport()
        svc = _make_service(transport=transport)

        with patch.multiple("app.extraction.tika", **mock_metrics):
            await svc.extract_text(b"data", "test.txt")

        mock_metrics["extraction_completed"].add.assert_called_once()
        args, kwargs = mock_metrics["extraction_completed"].add.call_args
        assert args[0] == 1
        assert args[1]["content_type"] == "text/plain"
        assert args[1]["ocr_applied"] == "false"

    @pytest.mark.asyncio
    async def test_failed_counter_on_error(self, mock_metrics):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/rmeta/text":
                return httpx.Response(500, request=request)
            return httpx.Response(404, request=request)

        transport = httpx.MockTransport(handler)
        svc = _make_service(transport=transport)

        with (
            patch.multiple("app.extraction.tika", **mock_metrics),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await svc.extract_text(b"data", "test.txt")

        mock_metrics["extraction_failed"].add.assert_called_once()
        args, _ = mock_metrics["extraction_failed"].add.call_args
        assert args[0] == 1
        assert args[1]["error_type"] == "HTTPStatusError"
        assert args[1]["content_type"] == "unknown"

    @pytest.mark.asyncio
    async def test_duration_recorded(self, mock_metrics):
        transport = _mock_transport()
        svc = _make_service(transport=transport)

        with patch.multiple("app.extraction.tika", **mock_metrics):
            await svc.extract_text(b"data", "test.txt")

        mock_metrics["extraction_duration_seconds"].record.assert_called_once()
        args, _ = mock_metrics["extraction_duration_seconds"].record.call_args
        assert args[0] > 0  # elapsed time is positive

    @pytest.mark.asyncio
    async def test_document_size_recorded(self, mock_metrics):
        transport = _mock_transport()
        svc = _make_service(transport=transport)

        with patch.multiple("app.extraction.tika", **mock_metrics):
            await svc.extract_text(b"data", "test.txt")

        mock_metrics["extraction_document_size_bytes"].record.assert_called_once()
        args, _ = mock_metrics["extraction_document_size_bytes"].record.call_args
        assert args[0] == 4  # len(b"data")

    @pytest.mark.asyncio
    async def test_text_length_recorded(self, mock_metrics):
        transport = _mock_transport(text_body="hello world")
        svc = _make_service(transport=transport)

        with patch.multiple("app.extraction.tika", **mock_metrics):
            await svc.extract_text(b"data", "test.txt")

        mock_metrics["extraction_text_length_chars"].record.assert_called_once()
        args, _ = mock_metrics["extraction_text_length_chars"].record.call_args
        assert args[0] == 11  # len("hello world")

    @pytest.mark.asyncio
    async def test_completed_counter_carries_ocr_attribute(self, mock_metrics):
        transport = _mock_transport(
            meta_body={
                "Content-Type": "image/png",
                "X-TIKA:Parsed-By": [
                    "org.apache.tika.parser.DefaultParser",
                    "org.apache.tika.parser.ocr.TesseractOCRParser",
                ],
            },
        )
        svc = _make_service(transport=transport)

        with patch.multiple("app.extraction.tika", **mock_metrics):
            await svc.extract_text(b"img", "scan.png", "image/png")

        args, _ = mock_metrics["extraction_completed"].add.call_args
        assert args[1]["ocr_applied"] == "true"
        assert args[1]["content_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_duration_recorded_on_failure(self, mock_metrics):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/rmeta/text":
                return httpx.Response(500, request=request)
            return httpx.Response(404, request=request)

        transport = httpx.MockTransport(handler)
        svc = _make_service(transport=transport)

        with (
            patch.multiple("app.extraction.tika", **mock_metrics),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await svc.extract_text(b"data", "test.txt")

        # Duration is recorded even on failure.
        mock_metrics["extraction_duration_seconds"].record.assert_called_once()
