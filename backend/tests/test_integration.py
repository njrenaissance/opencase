import httpx
import pytest


@pytest.mark.integration
async def test_health_endpoint_live() -> None:
    """Hit the running server to verify the health endpoint."""
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "OpenCase"
