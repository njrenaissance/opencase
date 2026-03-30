"""TikaExtractionService — async document text extraction via Apache Tika."""

from __future__ import annotations

import logging
import time
import urllib.parse

import httpx
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from app.core.config import ExtractionSettings
from app.core.metrics import (
    extraction_completed,
    extraction_document_size_bytes,
    extraction_duration_seconds,
    extraction_failed,
    extraction_text_length_chars,
)
from app.extraction.models import ExtractionResult

tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

# Tika metadata key that lists the parsers used for extraction.
_PARSED_BY_KEY = "X-TIKA:Parsed-By"
_OCR_PARSER = "org.apache.tika.parser.ocr.TesseractOCRParser"


class TikaExtractionService:
    """Extract text and metadata from documents via an Apache Tika server.

    Uses ``httpx.AsyncClient`` for non-blocking HTTP calls to the Tika
    REST API.  Respects all fields in :class:`ExtractionSettings`
    (timeout, max file size, OCR toggle, OCR languages).
    """

    def __init__(self, settings: ExtractionSettings) -> None:
        self._settings = settings

    # ------------------------------------------------------------------
    # Internal — client lifecycle
    # ------------------------------------------------------------------

    def _make_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._settings.tika_url,
            timeout=httpx.Timeout(self._settings.request_timeout),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract_text(
        self,
        document_bytes: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> ExtractionResult:
        """Extract plain text and metadata from a document.

        Args:
            document_bytes: Raw file content.
            filename: Original filename (passed to Tika via Content-Disposition).
            content_type: Optional MIME type hint.  Defaults to
                ``application/octet-stream`` which lets Tika auto-detect.

        Returns:
            An :class:`ExtractionResult` with extracted text and metadata.

        Raises:
            ValueError: If *document_bytes* exceeds the configured
                ``max_file_size_bytes``.
            httpx.HTTPStatusError: On non-2xx responses from Tika.
        """
        # Size validation intentionally runs before the span so that
        # rejected files are not counted as extraction failures.
        size = len(document_bytes)
        max_size = self._settings.max_file_size_bytes
        if size > max_size:
            raise ValueError(
                f"File size {size:,} bytes exceeds limit of {max_size:,} bytes"
            )

        with tracer.start_as_current_span(
            "extraction.extract_text",
            attributes={
                "extraction.filename": filename,
                "extraction.size_bytes": size,
                "extraction.content_type": content_type or "auto",
            },
        ) as span:
            start = time.monotonic()
            try:
                headers = self._build_headers(content_type, filename)
                headers["Accept"] = "application/json"

                async with self._make_client() as client:
                    # Single call to /rmeta/text returns text + metadata.
                    resp = await client.put(
                        "/rmeta/text",
                        content=document_bytes,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    payload = resp.json()

                # /rmeta returns a list; take the first (and usually only) entry.
                metadata = payload[0] if isinstance(payload, list) else payload

                text = metadata.pop("X-TIKA:content", "").strip()
                detected_type = metadata.get("Content-Type", content_type or "")
                language = metadata.get("language") or None
                ocr_applied = self._detect_ocr(metadata)

                # Enrich span with result attributes.
                span.set_attribute("extraction.text_length", len(text))
                span.set_attribute("extraction.ocr_applied", ocr_applied)
                span.set_attribute("extraction.detected_content_type", detected_type)
                if language:
                    span.set_attribute("extraction.language", language)

                # Record metrics.
                elapsed = time.monotonic() - start
                attrs = {
                    "content_type": detected_type,
                    "ocr_applied": "true" if ocr_applied else "false",
                }
                extraction_completed.add(1, attrs)
                extraction_duration_seconds.record(elapsed, attrs)
                extraction_document_size_bytes.record(size, attrs)
                extraction_text_length_chars.record(len(text), attrs)

                logger.info(
                    "Extracted %d chars from %s (ocr=%s, lang=%s)",
                    len(text),
                    filename,
                    ocr_applied,
                    language,
                )

                return ExtractionResult(
                    text=text,
                    content_type=detected_type,
                    metadata=metadata,
                    ocr_applied=ocr_applied,
                    language=language,
                )

            except Exception as exc:
                elapsed = time.monotonic() - start
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                # Use "unknown" on the error path — Tika never resolved the
                # type, so the caller-supplied hint (or lack thereof) would
                # create inconsistent cardinality vs the success path which
                # uses Tika's detected_type.
                error_ct = "unknown"
                extraction_failed.add(
                    1,
                    {
                        "content_type": error_ct,
                        "error_type": type(exc).__name__,
                    },
                )
                extraction_duration_seconds.record(
                    elapsed,
                    {
                        "content_type": error_ct,
                        "ocr_applied": "false",
                    },
                )
                raise

    async def health_check(self) -> bool:
        """Return ``True`` if the Tika server is reachable."""
        try:
            async with self._make_client() as client:
                resp = await client.get("/tika")
                return resp.status_code == 200
        except Exception:
            logger.warning("Tika health check failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(
        self,
        content_type: str | None,
        filename: str,
    ) -> dict[str, str]:
        # Always use application/octet-stream — Tika auto-detects the real
        # type and rejects some MIME types it doesn't recognise (e.g.
        # text/markdown) with 400.
        safe_name = urllib.parse.quote(filename, safe="")
        headers: dict[str, str] = {
            "Content-Type": "application/octet-stream",
            "Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}",
        }
        if not self._settings.ocr_enabled:
            headers["X-Tika-Skip-OcrAndOCR"] = "true"
        # Note: Tika 3.x does not support the X-Tika-OCRLanguages request
        # header and returns 400 if it is present.  OCR language is
        # configured server-side instead.  When OCR is enabled we simply
        # omit language headers and let Tika use its default (English).
        return headers

    @staticmethod
    def _detect_ocr(metadata: dict[str, object]) -> bool:
        parsed_by = metadata.get(_PARSED_BY_KEY, "")
        if isinstance(parsed_by, list):
            return any(_OCR_PARSER in p for p in parsed_by)
        return _OCR_PARSER in str(parsed_by)
