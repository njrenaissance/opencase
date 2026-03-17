"""Integration tests — OTel span delivery to Jaeger.

Verifies that FastAPI and SQLAlchemy instrumentation produce spans that arrive
in the Jaeger collector and are queryable via its REST API.

Requires the integration stack: postgres + fastapi + jaeger.
"""

import time

import httpx
import pytest

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _query_spans(jaeger_url: str, service: str) -> list[dict]:
    r = httpx.get(
        f"{jaeger_url}/api/traces",
        params={"service": service, "limit": 20},
        timeout=5,
    )
    r.raise_for_status()
    spans: list[dict] = []
    for trace in r.json().get("data", []):
        spans.extend(trace.get("spans", []))
    return spans


def _wait_for_span(
    jaeger_url: str,
    service: str,
    operation_fragment: str,
    timeout: float = 10.0,
) -> list[dict]:
    """Poll Jaeger until a span matching operation_fragment appears."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        spans = _query_spans(jaeger_url, service)
        matching = [
            s for s in spans if operation_fragment in s.get("operationName", "")
        ]
        if matching:
            return matching
        time.sleep(0.5)
    return []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_health_span_in_jaeger(fastapi_service: str, jaeger_service: str) -> None:
    """GET /health produces a span that arrives in Jaeger."""
    r = httpx.get(f"{fastapi_service}/health", timeout=5)
    assert r.status_code == 200

    spans = _wait_for_span(jaeger_service, "opencase-api", "GET /health")
    assert spans, "No 'GET /health' span found in Jaeger"


def test_ready_sqlalchemy_span_in_jaeger(
    fastapi_service: str, jaeger_service: str
) -> None:
    """GET /ready produces a SQLAlchemy SELECT span that arrives in Jaeger."""
    r = httpx.get(f"{fastapi_service}/ready", timeout=5)
    assert r.status_code == 200

    spans = _wait_for_span(jaeger_service, "opencase-api", "SELECT")
    assert spans, (
        "No 'SELECT' span found in Jaeger — SQLAlchemy instrumentation may not be wired"
    )
