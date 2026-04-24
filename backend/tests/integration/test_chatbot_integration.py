"""Docker-based integration tests for chatbot configuration and Ollama health.

These tests require the full docker compose stack to be running and are
skipped in unit-test CI runs.

Run manually:
    docker compose up -d
    pytest tests/integration/ -m integration -v
"""

import httpx
import pytest

BASE_URL = "http://localhost:8000"

pytestmark = pytest.mark.integration


@pytest.fixture
async def http_client(fastapi_service):
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        yield client


async def test_ready_includes_ollama_service(http_client):
    """GET /ready should include 'ollama' key in services dict."""
    response = await http_client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert "ollama" in body["services"]


async def test_ollama_health_ok_when_model_loaded(http_client):
    """With docker compose running (ollama-init has completed model pulls),
    the ollama service status should be 'ok'."""
    response = await http_client.get("/ready")
    body = response.json()
    assert body["services"]["ollama"] == "ok", (
        "Ollama health check failed. Ensure 'docker compose up' has completed "
        "and ollama-init has finished pulling the configured LLM model."
    )


async def test_overall_readiness_ok_with_full_stack(http_client):
    """Overall readiness is 'ok' when all services including Ollama are healthy."""
    response = await http_client.get("/ready")
    body = response.json()
    assert body["status"] == "ok", (
        f"One or more services are not ready: {body.get('services')}"
    )
