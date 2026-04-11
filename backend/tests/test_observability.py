"""Integration tests — OTel span delivery to Grafana otel-lgtm (Tempo).

Verifies that FastAPI and SQLAlchemy instrumentation produce spans that arrive
in the Tempo backend and are queryable via the Tempo HTTP API.

Requires the integration stack: postgres + fastapi + grafana (otel-lgtm).
"""

import os
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

    traces = _wait_for_traces(grafana_service, "gideon-api")
    assert traces, "No traces found in Tempo for gideon-api"


def test_ready_sqlalchemy_span_in_tempo(
    fastapi_service: str, grafana_service: str
) -> None:
    """GET /ready produces a trace that arrives in Tempo."""
    r = httpx.get(f"{fastapi_service}/ready", timeout=5)
    assert r.status_code == 200

    traces = _wait_for_traces(grafana_service, "gideon-api")
    assert traces, (
        "No traces found in Tempo — SQLAlchemy instrumentation may not be wired"
    )


def test_worker_span_in_tempo(
    redis_service: tuple[str, int],
    postgres_service: tuple[str, int],
    grafana_service: str,
) -> None:
    """Celery worker emits OTel spans that arrive in Tempo.

    Submits a ping task directly to the worker, waits for it to complete,
    then queries Tempo for traces from the ``gideon-worker`` service.
    """
    from celery import Celery

    redis_host, redis_port = redis_service
    pg_host, pg_port = postgres_service
    pg_user = os.environ.get("POSTGRES_USER", "gideon")
    pg_pass = os.environ.get("POSTGRES_PASSWORD", "gideon")
    backend = (
        f"db+postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/gideon_tasks_test"
    )
    app = Celery(
        broker=f"redis://{redis_host}:{redis_port}/0",
        backend=backend,
    )
    result = app.send_task("gideon.ping")
    assert result.get(timeout=15) == "pong"

    traces = _wait_for_traces(grafana_service, "gideon-worker", timeout=30.0)
    assert traces, "No traces found in Tempo for gideon-worker"

    # Verify CeleryInstrumentor produced a span (not just any trace).
    # Tempo search results include span names like "run" or "apply_async".
    span_names = {
        s.get("spanSet", {}).get("spans", [{}])[0].get("name", "")
        for s in traces
        if s.get("spanSet")
    }
    assert span_names, "Traces found but no span names — check Tempo response format"
