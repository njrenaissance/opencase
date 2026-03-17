"""Step definitions for observability.feature.

Verifies that spans produced by FastAPI and SQLAlchemy instrumentation
are delivered to the Jaeger collector and queryable via its REST API.

All scenarios require the integration stack (postgres + fastapi + jaeger).
"""

import time

import httpx
import pytest
from pytest_bdd import given, scenarios, then, when

pytestmark = [pytest.mark.integration]

scenarios("api/observability.feature")

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_fastapi_url: str = ""
_jaeger_url: str = ""
_last_spans: list[dict] = []


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
# Steps
# ---------------------------------------------------------------------------


@given("the integration stack is running with OTLP tracing enabled")
def stack_running(fastapi_service: str, jaeger_service: str) -> None:
    global _fastapi_url, _jaeger_url  # noqa: PLW0603
    _fastapi_url = fastapi_service
    _jaeger_url = jaeger_service


@when("I send GET /health to the FastAPI service")
def get_health() -> None:
    r = httpx.get(f"{_fastapi_url}/health", timeout=5)
    assert r.status_code == 200


@when("I send GET /ready to the FastAPI service")
def get_ready() -> None:
    r = httpx.get(f"{_fastapi_url}/ready", timeout=5)
    assert r.status_code == 200


@then('Jaeger contains a trace for service "opencase-api"')
def jaeger_has_traces() -> None:
    global _last_spans  # noqa: PLW0603
    spans = _query_spans(_jaeger_url, "opencase-api")
    assert spans, "No traces found in Jaeger for service 'opencase-api'"
    _last_spans = spans


@then("that trace includes a span with operation name containing {fragment}")
def span_contains_operation(fragment: str) -> None:
    fragment = fragment.strip('"')
    matching = _wait_for_span(_jaeger_url, "opencase-api", fragment)
    assert matching, (
        f"No span with operation name containing '{fragment}' found in Jaeger"
    )
