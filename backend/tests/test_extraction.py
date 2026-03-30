"""Unit tests for the extraction module."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import ExtractionSettings
from app.extraction.models import ExtractionResult
from app.extraction.tika import TikaExtractionService

# ---------------------------------------------------------------------------
# ExtractionResult
# ---------------------------------------------------------------------------


class TestExtractionResult:
    def test_to_dict_all_fields(self):
        result = ExtractionResult(
            text="Hello world",
            content_type="text/plain",
            metadata={"author": "test"},
            ocr_applied=True,
            language="en",
        )
        d = result.to_dict()
        assert d == {
            "text": "Hello world",
            "content_type": "text/plain",
            "metadata": {"author": "test"},
            "ocr_applied": True,
            "language": "en",
        }

    def test_to_dict_defaults(self):
        result = ExtractionResult(text="", content_type="application/pdf")
        d = result.to_dict()
        assert d["metadata"] == {}
        assert d["ocr_applied"] is False
        assert d["language"] is None

    def test_frozen(self):
        result = ExtractionResult(text="x", content_type="text/plain")
        with pytest.raises(AttributeError):
            result.text = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TikaExtractionService helpers
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
    meta_body: dict | list | None = None,
    text_status: int = 200,
    meta_status: int = 200,
) -> httpx.MockTransport:
    """Return a transport that responds to PUT /tika and PUT /meta."""
    if meta_body is None:
        meta_body = {"Content-Type": "text/plain", "language": "en"}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/tika" and request.method == "PUT":
            return httpx.Response(text_status, text=text_body, request=request)
        if request.url.path == "/meta" and request.method == "PUT":
            return httpx.Response(meta_status, json=meta_body, request=request)
        if request.url.path == "/tika" and request.method == "GET":
            return httpx.Response(200, text="Apache Tika 3.1.0", request=request)
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
            return httpx.AsyncClient(
                transport=transport,
                base_url=s.tika_url,
            )

        svc._make_client = _patched_client  # type: ignore[method-assign]
    return svc


# ---------------------------------------------------------------------------
# TikaExtractionService.extract_text
# ---------------------------------------------------------------------------


class TestExtractText:
    @pytest.mark.asyncio
    async def test_success(self):
        transport = _mock_transport(
            text_body="Hello world",
            meta_body={"Content-Type": "application/pdf", "language": "en"},
        )
        svc = _make_service(transport=transport)

        result = await svc.extract_text(b"fake pdf", "test.pdf", "application/pdf")

        assert result.text == "Hello world"
        assert result.content_type == "application/pdf"
        assert result.language == "en"
        assert result.ocr_applied is False

    @pytest.mark.asyncio
    async def test_success_with_list_metadata(self):
        """Tika sometimes returns metadata as a single-element list."""
        transport = _mock_transport(
            text_body="content",
            meta_body=[{"Content-Type": "text/plain", "language": "fr"}],
        )
        svc = _make_service(transport=transport)

        result = await svc.extract_text(b"data", "test.txt")
        assert result.content_type == "text/plain"
        assert result.language == "fr"

    @pytest.mark.asyncio
    async def test_ocr_detected(self):
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

        result = await svc.extract_text(b"img", "scan.png", "image/png")
        assert result.ocr_applied is True

    @pytest.mark.asyncio
    async def test_file_too_large(self):
        svc = _make_service(settings=_make_settings(max_file_size_bytes=10))

        with pytest.raises(ValueError, match="exceeds limit"):
            await svc.extract_text(b"x" * 11, "big.pdf")

    @pytest.mark.asyncio
    async def test_ocr_disabled_headers(self):
        """When OCR is disabled, X-Tika-Skip-OcrAndOCR header should be set."""
        requests_sent: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_sent.append(request)
            if request.url.path == "/tika":
                return httpx.Response(200, text="text", request=request)
            if request.url.path == "/meta":
                return httpx.Response(
                    200,
                    json={"Content-Type": "text/plain"},
                    request=request,
                )
            return httpx.Response(404, request=request)

        transport = httpx.MockTransport(handler)
        svc = _make_service(
            settings=_make_settings(ocr_enabled=False),
            transport=transport,
        )

        await svc.extract_text(b"data", "test.txt")

        tika_req = next(r for r in requests_sent if r.url.path == "/tika")
        assert tika_req.headers["X-Tika-Skip-OcrAndOCR"] == "true"
        assert "X-Tika-OCRLanguages" not in tika_req.headers

    @pytest.mark.asyncio
    async def test_ocr_enabled_no_language_header(self):
        """When OCR is enabled, no OCR headers are sent (Tika 3.x)."""
        requests_sent: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_sent.append(request)
            if request.url.path == "/tika":
                return httpx.Response(200, text="text", request=request)
            if request.url.path == "/meta":
                return httpx.Response(
                    200,
                    json={"Content-Type": "text/plain"},
                    request=request,
                )
            return httpx.Response(404, request=request)

        transport = httpx.MockTransport(handler)
        svc = _make_service(
            settings=_make_settings(ocr_enabled=True, ocr_languages="eng+fra"),
            transport=transport,
        )

        await svc.extract_text(b"data", "test.txt")

        tika_req = next(r for r in requests_sent if r.url.path == "/tika")
        assert "X-Tika-OCRLanguages" not in tika_req.headers
        assert "X-Tika-Skip-OcrAndOCR" not in tika_req.headers

    @pytest.mark.asyncio
    async def test_always_sends_octet_stream_content_type(self):
        """Content-Type is always application/octet-stream regardless of caller hint."""
        requests_sent: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_sent.append(request)
            if request.url.path == "/tika":
                return httpx.Response(200, text="text", request=request)
            if request.url.path == "/meta":
                return httpx.Response(
                    200,
                    json={"Content-Type": "text/plain"},
                    request=request,
                )
            return httpx.Response(404, request=request)

        transport = httpx.MockTransport(handler)
        svc = _make_service(transport=transport)

        # Even when caller passes text/markdown, we send octet-stream
        await svc.extract_text(b"data", "test.md", "text/markdown")

        tika_req = next(r for r in requests_sent if r.url.path == "/tika")
        assert tika_req.headers["Content-Type"] == "application/octet-stream"


# ---------------------------------------------------------------------------
# TikaExtractionService.health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy(self):
        transport = _mock_transport()
        svc = _make_service(transport=transport)
        assert await svc.health_check() is True

    @pytest.mark.asyncio
    async def test_unhealthy_connection_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = httpx.MockTransport(handler)
        svc = _make_service(transport=transport)
        assert await svc.health_check() is False

    @pytest.mark.asyncio
    async def test_unhealthy_non_200(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, request=request)

        transport = httpx.MockTransport(handler)
        svc = _make_service(transport=transport)
        assert await svc.health_check() is False


# ---------------------------------------------------------------------------
# Factory singleton
# ---------------------------------------------------------------------------


class TestFactory:
    def test_returns_same_instance(self):
        import app.extraction as extraction_mod

        # Reset singleton
        extraction_mod._service = None
        try:
            svc1 = extraction_mod.get_extraction_service()
            svc2 = extraction_mod.get_extraction_service()
            assert svc1 is svc2
        finally:
            extraction_mod._service = None

    def test_uses_settings(self):
        import app.extraction as extraction_mod

        extraction_mod._service = None
        try:
            svc = extraction_mod.get_extraction_service()
            from app.core.config import settings

            assert svc._settings is settings.extraction
        finally:
            extraction_mod._service = None
