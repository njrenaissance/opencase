"""Unit tests for health and readiness endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

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


def _mock_minio_ok():
    """Return a patch that stubs urlopen so check_minio returns 'ok'."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return patch("app.api.health.urlopen", return_value=mock_resp)


def _override_get_db(mock_session):
    from app.db import get_db

    async def _get_db():
        yield mock_session

    app.dependency_overrides[get_db] = _get_db


@_mock_minio_ok()
@_mock_aioredis_ok()
async def test_ready_postgres_ok(_mock_redis, _mock_minio, client):
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


@_mock_minio_ok()
@_mock_aioredis_ok()
async def test_ready_postgres_error(_mock_redis, _mock_minio, client):
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


@_mock_minio_ok()
@_mock_aioredis_ok()
async def test_ready_redis_ok(_mock_redis, _mock_minio, client):
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


@_mock_minio_ok()
@patch(
    "app.api.health.aioredis.from_url",
    side_effect=ConnectionError("Redis unavailable"),
)
async def test_ready_redis_error(_mock_from_url, _mock_minio, client):
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


@_mock_aioredis_ok()
@_mock_minio_ok()
async def test_ready_minio_ok(_mock_minio, _mock_redis, client):
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    _override_get_db(mock_session)
    try:
        response = await client.get("/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["services"]["minio"] == "ok"
    finally:
        app.dependency_overrides.clear()


@_mock_aioredis_ok()
@patch("app.api.health.urlopen", side_effect=ConnectionError("MinIO unavailable"))
async def test_ready_minio_error(_mock_urlopen, _mock_redis, client):
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    _override_get_db(mock_session)
    try:
        response = await client.get("/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["services"]["minio"] == "error"
    finally:
        app.dependency_overrides.clear()
