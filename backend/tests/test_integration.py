"""Integration tests that run against the live compose stack.

pytest-docker manages the stack lifecycle (up/down with volume wipe).
These tests require Docker to be running.

Run with: pytest -m integration tests/test_integration.py
"""

import httpx
import pytest
import redis as redis_lib


@pytest.mark.integration
async def test_health_endpoint_live(fastapi_service: str) -> None:
    """Health endpoint returns 200 with correct payload."""
    async with httpx.AsyncClient(base_url=fastapi_service) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "OpenCase"


@pytest.mark.integration
async def test_ready_endpoint_postgres_ok(fastapi_service: str) -> None:
    """Readiness probe reports postgres=ok against the test database."""
    async with httpx.AsyncClient(base_url=fastapi_service) as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["services"]["postgres"] == "ok"


@pytest.mark.integration
def test_redis_ping(redis_service: tuple[str, int]) -> None:
    """Redis responds to PING from the host."""
    host, port = redis_service
    r = redis_lib.Redis(host=host, port=port, socket_timeout=2)
    assert r.ping() is True
    r.close()


@pytest.mark.integration
async def test_ready_endpoint_redis_ok(fastapi_service: str) -> None:
    """Readiness probe reports redis=ok against the test Redis."""
    async with httpx.AsyncClient(base_url=fastapi_service) as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["services"]["redis"] == "ok"


@pytest.mark.integration
def test_celery_worker_ping_task(
    redis_service: tuple[str, int],
    postgres_service: tuple[str, int],
) -> None:
    """Submit ping task to Celery worker and verify it returns 'pong'."""
    from celery import Celery

    from app.core.config import settings

    host, port = redis_service
    app = Celery(
        broker=f"redis://{host}:{port}/0",
        backend=settings.celery.result_backend,
    )
    result = app.send_task("opencase.ping")
    assert result.get(timeout=15) == "pong"
