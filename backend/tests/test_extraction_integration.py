"""Integration tests for TikaExtractionService against a live Tika container.

Requires the Docker stack to be running (``pytest -m integration``).
"""

from __future__ import annotations

import pytest

from app.core.config import ExtractionSettings
from app.extraction.tika import TikaExtractionService


def _make_service(host: str, port: int) -> TikaExtractionService:
    settings = ExtractionSettings(
        tika_url=f"http://{host}:{port}",
        ocr_enabled=True,
        ocr_languages="eng",
        request_timeout=30,
        max_file_size_bytes=100 * 1024 * 1024,
    )
    return TikaExtractionService(settings)


# TODO: All tests in TestTikaLive fail — TikaExtractionService has no .close() method.
# Remove the await svc.close() calls or add a close() method to the service.
@pytest.mark.integration
class TestTikaLive:
    @pytest.mark.asyncio
    async def test_health_check(self, tika_service):
        host, port = tika_service
        svc = _make_service(host, port)
        try:
            assert await svc.health_check() is True
        finally:
            await svc.close()

    @pytest.mark.asyncio
    async def test_extract_plain_text(self, tika_service):
        host, port = tika_service
        svc = _make_service(host, port)
        try:
            result = await svc.extract_text(
                b"Hello from OpenCase integration test",
                "test.txt",
                "text/plain",
            )
            assert "Hello from OpenCase" in result.text
            assert result.content_type  # Tika should detect a type
            assert result.ocr_applied is False
        finally:
            await svc.close()

    @pytest.mark.asyncio
    async def test_extract_pdf(self, tika_service):
        """Extract text from a minimal valid PDF."""
        host, port = tika_service
        svc = _make_service(host, port)

        # Minimal PDF containing the text "OpenCase Test"
        pdf_bytes = (
            b"%PDF-1.0\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]"
            b"/Contents 4 0 R/Parent 2 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
            b"4 0 obj<</Length 44>>stream\n"
            b"BT /F1 12 Tf 100 700 Td (OpenCase Test) Tj ET\n"
            b"endstream\nendobj\n"
            b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
            b"xref\n0 6\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"0000000266 00000 n \n"
            b"0000000360 00000 n \n"
            b"trailer<</Size 6/Root 1 0 R>>\n"
            b"startxref\n430\n%%EOF"
        )

        try:
            result = await svc.extract_text(pdf_bytes, "test.pdf", "application/pdf")
            assert "OpenCase Test" in result.text
            assert "pdf" in result.content_type.lower()
        finally:
            await svc.close()
