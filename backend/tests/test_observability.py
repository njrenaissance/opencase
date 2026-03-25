"""Integration tests — OTel span delivery to Grafana otel-lgtm (Tempo).

Verifies that FastAPI and SQLAlchemy instrumentation produce spans that arrive
in the Tempo backend and are queryable via the Tempo HTTP API.

Requires the integration stack: postgres + fastapi + grafana (otel-lgtm).
"""

import time

import httpx
import pytest

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _query_tempo_search(grafana_url: str, service: str) -> list[dict]:
    """Search Tempo for recent traces via the Grafana datasource proxy.

    The otel-lgtm image pre-provisions a Tempo datasource with uid "tempo".
    Tempo's own HTTP API (port 3200) is internal to the container, so we
    query through Grafana's datasource proxy on the mapped port.
    """
    r = httpx.get(
        f"{grafana_url}/api/datasources/proxy/uid/tempo/api/search",
        params={"q": f'{{ resource.service.name = "{service}" }}', "limit": 20},
        timeout=5,
    )
    if r.status_code != 200:
        return []
    return r.json().get("traces", [])


def _wait_for_traces(
    grafana_url: str,
    service: str,
    timeout: float = 15.0,
) -> list[dict]:
    """Poll Tempo until traces for the given service appear."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        traces = _query_tempo_search(grafana_url, service)
        if traces:
            return traces
        time.sleep(1.0)
    return []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_health_span_in_tempo(fastapi_service: str, grafana_service: str) -> None:
    """GET /health produces a span that arrives in Tempo."""
    r = httpx.get(f"{fastapi_service}/health", timeout=5)
    assert r.status_code == 200

    traces = _wait_for_traces(grafana_service, "opencase-api")
    assert traces, "No traces found in Tempo for opencase-api"


def test_ready_sqlalchemy_span_in_tempo(
    fastapi_service: str, grafana_service: str
) -> None:
    """GET /ready produces a trace that arrives in Tempo."""
    r = httpx.get(f"{fastapi_service}/ready", timeout=5)
    assert r.status_code == 200

    traces = _wait_for_traces(grafana_service, "opencase-api")
    assert traces, (
        "No traces found in Tempo — SQLAlchemy instrumentation may not be wired"
    )


def test_worker_span_in_tempo(
    redis_service: tuple[str, int],
    postgres_service: tuple[str, int],  # noqa: ARG001 — ensures Postgres is up for result backend
    grafana_service: str,
) -> None:
    """Celery worker emits OTel spans that arrive in Tempo.

    Submits a ping task directly to the worker, waits for it to complete,
    then queries Tempo for traces from the ``opencase-worker`` service.
    """
    from celery import Celery

    from app.core.config import settings

    host, port = redis_service
    app = Celery(
        broker=f"redis://{host}:{port}/0",
        backend=settings.celery.result_backend,
    )
    result = app.send_task("opencase.ping")
    assert result.get(timeout=15) == "pong"

    traces = _wait_for_traces(grafana_service, "opencase-worker", timeout=30.0)
    assert traces, "No traces found in Tempo for opencase-worker"
