"""Unit tests for health and readiness endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "OpenCase"
    assert "version" in body


def _mock_aioredis_ok():
    """Return a patch that stubs aioredis.from_url with a healthy async mock."""
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()
    return patch("app.api.health.aioredis.from_url", return_value=mock_redis)


def _override_get_db(mock_session):
    from app.db import get_db

    async def _get_db():
        yield mock_session

    app.dependency_overrides[get_db] = _get_db


@_mock_aioredis_ok()
async def test_ready_postgres_ok(_mock_redis, client):
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    _override_get_db(mock_session)
    try:
        response = await client.get("/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["services"]["postgres"] == "ok"
    finally:
        app.dependency_overrides.clear()


@_mock_aioredis_ok()
async def test_ready_postgres_error(_mock_redis, client):
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        side_effect=OperationalError("conn", {}, Exception())
    )
    _override_get_db(mock_session)
    try:
        response = await client.get("/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["services"]["postgres"] == "error"
    finally:
        app.dependency_overrides.clear()


@_mock_aioredis_ok()
async def test_ready_redis_ok(_mock_redis, client):
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    _override_get_db(mock_session)
    try:
        response = await client.get("/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["services"]["redis"] == "ok"
    finally:
        app.dependency_overrides.clear()


@patch(
    "app.api.health.aioredis.from_url",
    side_effect=ConnectionError("Redis unavailable"),
)
async def test_ready_redis_error(_mock_from_url, client):
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    _override_get_db(mock_session)
    try:
        response = await client.get("/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["services"]["redis"] == "error"
    finally:
        app.dependency_overrides.clear()
