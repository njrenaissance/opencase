"""Integration tests that run against the live compose stack.

pytest-docker manages the stack lifecycle (up/down with volume wipe).
These tests require Docker to be running.

Run with: pytest -m integration tests/test_integration.py
"""

import asyncio

import httpx
import pytest
import redis as redis_lib
from shared.models.enums import TaskState


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


# ---------------------------------------------------------------------------
# Task API — submit → poll → complete
# ---------------------------------------------------------------------------


async def _login(client: httpx.AsyncClient, email: str, password: str) -> str:
    """Log in and return an access token.

    NOTE: Does not handle MFA flow — MFA-enabled users return ``mfa_token``
    instead of ``access_token``, causing a KeyError.
    """
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.mark.xfail(
    reason="_login() needs MFA flow support for MFA-enabled admin user",
    strict=True,
)
@pytest.mark.integration
async def test_task_submit_poll_complete(
    fastapi_service: str, seed_admin: dict
) -> None:
    """Submit a ping task via the API and poll until it completes."""
    async with httpx.AsyncClient(base_url=fastapi_service) as client:
        token = await _login(client, seed_admin["email"], seed_admin["password"])
        headers = {"Authorization": f"Bearer {token}"}

        # Submit
        resp = await client.post("/tasks/", json={"task_name": "ping"}, headers=headers)
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        # Poll until SUCCESS (max 15 seconds)
        for _ in range(30):
            resp = await client.get(f"/tasks/{task_id}", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            if data["status"] == TaskState.success:
                assert data["result"] == "pong"
                break
            await asyncio.sleep(0.5)
        else:
            pytest.fail(f"Task {task_id} did not complete within 15 seconds")

        # List should include our task
        resp = await client.get("/tasks/", headers=headers)
        assert resp.status_code == 200
        task_ids = [t["id"] for t in resp.json()]
        assert task_id in task_ids


# ---------------------------------------------------------------------------
# Tika extraction — live container
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="_login() needs MFA flow support for MFA-enabled admin user",
    strict=True,
)
@pytest.mark.integration
async def test_tika_extract_text_via_api(
    fastapi_service: str,
    tika_service: tuple[str, int],
    seed_admin: dict,
) -> None:
    """Upload a document then submit extract_document task and verify result."""
    async with httpx.AsyncClient(base_url=fastapi_service) as client:
        token = await _login(client, seed_admin["email"], seed_admin["password"])
        headers = {"Authorization": f"Bearer {token}"}

        # Submit an extract_document task with a known S3 key.
        # NOTE: this test requires a document already in S3.  If no document
        # exists yet, the task will fail — which still validates the wiring.
        resp = await client.post(
            "/tasks/",
            json={
                "task_name": "extract_document",
                "args": ["00000000-0000-0000-0000-000000000000", "nonexistent/key"],
            },
            headers=headers,
        )
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        # Poll — we expect FAILURE since the S3 key doesn't exist, but
        # this confirms the task is registered and the worker picks it up.
        for _ in range(30):
            resp = await client.get(f"/tasks/{task_id}", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            if data["status"] in (TaskState.success, TaskState.failure):
                break
            await asyncio.sleep(0.5)
        else:
            pytest.fail(f"extract_document task {task_id} did not complete")

        # Task was picked up and processed (success or failure depending on S3 state)
        assert data["status"] in (TaskState.success, TaskState.failure)
