"""Integration tests for the backend Docker image.

These tests build the Docker image and verify the container works.
All tests require Docker to be running and are marked as integration
tests — they are skipped during normal unit test runs.

Run with: uv run pytest -m integration tests/test_docker.py -v
"""

import subprocess
import time

import httpx
import pytest

IMAGE_TAG = "opencase-api:test"
DOCKERFILE = "docker/Dockerfile"
BUILD_CONTEXT = "."


@pytest.fixture(scope="session")
def docker_image():
    """Build the Docker image once per test session."""
    result = subprocess.run(
        ["docker", "build", "-f", DOCKERFILE, "-t", IMAGE_TAG, BUILD_CONTEXT],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert result.returncode == 0, f"Docker build failed:\n{result.stderr}"
    yield IMAGE_TAG
    subprocess.run(["docker", "rmi", IMAGE_TAG], capture_output=True)


@pytest.mark.integration
def test_image_builds(docker_image):
    """The Docker image builds successfully."""
    result = subprocess.run(
        ["docker", "image", "inspect", docker_image],
        capture_output=True,
    )
    assert result.returncode == 0


@pytest.mark.integration
def test_app_imports(docker_image):
    """The app package imports inside the container."""
    result = subprocess.run(
        ["docker", "run", "--rm", docker_image, "python", "-c", "import app"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Import failed:\n{result.stderr}"


@pytest.mark.integration
def test_runs_as_non_root(docker_image):
    """The container runs as the opencase user, not root."""
    result = subprocess.run(
        ["docker", "run", "--rm", docker_image, "whoami"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "opencase"


@pytest.mark.integration
def test_health_endpoint(docker_image):
    """The /health endpoint returns 200 with expected JSON."""
    container_name = "opencase-api-test"

    # Start the container
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-p",
            "18000:8000",
            docker_image,
        ],
        capture_output=True,
        check=True,
    )

    try:
        # Wait for the server to be ready
        for _ in range(30):
            try:
                resp = httpx.get("http://localhost:18000/health", timeout=2)
                if resp.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.RemoteProtocolError):
                time.sleep(1)
        else:
            pytest.fail("Container did not become healthy within 30 seconds")

        data = resp.json()
        assert data["status"] == "ok"
        assert data["app"] == "OpenCase"
        assert "version" in data
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
