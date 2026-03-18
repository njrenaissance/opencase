import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load test environment before any app imports.
# Required fields (OPENCASE_AUTH_SECRET_KEY, OPENCASE_DB_URL) must be set
# before config.py is imported, because Settings() is instantiated at module level.
_ENV_TEST = Path(__file__).parent.parent / ".env.test"
load_dotenv(_ENV_TEST)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import create_engine, delete  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.auth import hash_password  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.models.firm import Firm  # noqa: E402
from app.db.models.refresh_token import RefreshToken  # noqa: E402
from app.db.models.user import Role, User  # noqa: E402
from app.main import app  # noqa: E402

# ---------------------------------------------------------------------------
# Paths used by pytest-docker
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent.parent
_COMPOSE_BASE = _REPO_ROOT / "infrastructure" / "docker-compose.yml"
_COMPOSE_INTEGRATION = _REPO_ROOT / "infrastructure" / "docker-compose.integration.yml"


# ---------------------------------------------------------------------------
# Unit test client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# pytest-docker — integration test stack lifecycle
#
# Dev mode:  docker compose up  (uses root .env, data persists in 'opencase' DB)
# Test mode: pytest -m integration  (pytest-docker manages the stack lifecycle,
#            uses .env.test, fastapi points at 'opencase_test', volumes wiped
#            on teardown so each run starts from a clean database)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def docker_compose_file():
    return [str(_COMPOSE_BASE), str(_COMPOSE_INTEGRATION)]


@pytest.fixture(scope="session")
def docker_compose_command():
    return f"docker compose --env-file {_ENV_TEST}"


@pytest.fixture(scope="session")
def docker_compose_project_name():
    # Separate project name prevents conflicts with the dev stack
    return "opencase-test"


@pytest.fixture(scope="session")
def docker_cleanup():
    # Down with -v wipes volumes so opencase_test is reset between runs
    return "down --volumes"


def _api_ready(url: str) -> bool:
    try:
        return httpx.get(f"{url}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def _jaeger_ready(host: str, port: int) -> bool:
    try:
        return httpx.get(f"http://{host}:{port}/", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def _pg_ready(host: str, port: int) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def postgres_service(docker_ip, docker_services):
    """Ensure postgres is up and return (host, port).

    Used by test_db_schema.py so it shares the same pytest-docker lifecycle
    as the HTTP integration tests — one stack, one teardown, one volume wipe.
    """
    docker_services.wait_until_responsive(
        timeout=60.0,
        pause=0.5,
        check=lambda: _pg_ready(docker_ip, 5432),
    )
    return docker_ip, 5432


@pytest.fixture(scope="session")
def jaeger_service(docker_ip, docker_services):
    """Wait for Jaeger to be ready and return the query API base URL."""
    docker_services.wait_until_responsive(
        timeout=60.0,
        pause=0.5,
        check=lambda: _jaeger_ready(docker_ip, 16686),
    )
    return f"http://{docker_ip}:16686"


@pytest.fixture(scope="session")
def fastapi_service(docker_ip, docker_services):
    """Start the integration compose stack and return the FastAPI base URL.

    Requires Docker to be running. The stack is torn down (with volumes)
    after the test session completes, leaving no residual data.
    """
    url = f"http://{docker_ip}:8000"
    docker_services.wait_until_responsive(
        timeout=60.0,
        pause=0.5,
        check=lambda: _api_ready(url),
    )
    return url


# ---------------------------------------------------------------------------
# seed_admin — integration test user fixture
# ---------------------------------------------------------------------------

_SEED_ADMIN_EMAIL = "admin@opencase.test"
_SEED_ADMIN_PASSWORD = "integration-test-pw"  # noqa: S105


def _sync_db_url() -> str:
    """Convert async DSN to sync for direct DB access."""
    url = settings.db.url
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    return url


@pytest.fixture
def seed_admin(postgres_service):
    """Insert an admin user into the test DB, yield credentials, then clean up.

    Connects directly to the test database (opencase_test) — never touches
    the dev database.
    """
    engine = create_engine(_sync_db_url())
    firm_id = uuid.uuid4()
    user_id = uuid.uuid4()

    with Session(engine) as session:
        session.add(Firm(id=firm_id, name="Test Firm"))
        session.flush()
        session.add(
            User(
                id=user_id,
                firm_id=firm_id,
                email=_SEED_ADMIN_EMAIL,
                hashed_password=hash_password(_SEED_ADMIN_PASSWORD),
                first_name="Admin",
                last_name="Test",
                role=Role.admin,
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        session.commit()

    yield {
        "user_id": user_id,
        "firm_id": firm_id,
        "email": _SEED_ADMIN_EMAIL,
        "password": _SEED_ADMIN_PASSWORD,
    }

    # Teardown — remove all traces.
    with Session(engine) as session:
        session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
        session.execute(delete(User).where(User.id == user_id))
        session.execute(delete(Firm).where(Firm.id == firm_id))
        session.commit()

    engine.dispose()
