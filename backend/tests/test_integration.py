"""Integration tests that run against the live compose stack.

pytest-docker manages the stack lifecycle (up/down with volume wipe).
These tests require Docker to be running.

Run with: pytest -m integration tests/test_integration.py
"""

import httpx
import pytest


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
