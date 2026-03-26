"""MinIO integration tests — Feature 3.1.

Verifies bucket creation, object upload, and retrieval against the live
MinIO container managed by pytest-docker.

Run with: pytest -m integration tests/test_minio_integration.py
"""

import io

import httpx
import pytest
from minio import Minio

_ACCESS_KEY = "opencase"
_SECRET_KEY = "changeme"  # noqa: S105
_BUCKET = "opencase"


def _minio_client(host: str, port: int) -> Minio:
    return Minio(
        f"{host}:{port}",
        access_key=_ACCESS_KEY,
        secret_key=_SECRET_KEY,
        secure=False,
    )


@pytest.mark.integration
async def test_ready_endpoint_includes_minio(fastapi_service: str) -> None:
    """Readiness probe reports minio=ok."""
    async with httpx.AsyncClient(base_url=fastapi_service) as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["services"]["minio"] == "ok"


@pytest.mark.integration
def test_minio_bucket_exists(minio_service: tuple[str, int]) -> None:
    """The opencase bucket exists after minio-init runs."""
    host, port = minio_service
    client = _minio_client(host, port)
    assert client.bucket_exists(_BUCKET)


@pytest.mark.integration
def test_minio_put_get_object(minio_service: tuple[str, int]) -> None:
    """Upload a test object and retrieve it byte-for-byte."""
    host, port = minio_service
    client = _minio_client(host, port)

    test_data = b"hello opencase"
    object_name = "test/integration-test.txt"

    # PUT
    client.put_object(
        _BUCKET,
        object_name,
        io.BytesIO(test_data),
        length=len(test_data),
        content_type="text/plain",
    )

    # GET
    response = client.get_object(_BUCKET, object_name)
    try:
        retrieved = response.read()
    finally:
        response.close()
        response.release_conn()

    assert retrieved == test_data

    # Cleanup
    client.remove_object(_BUCKET, object_name)
