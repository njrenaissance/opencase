import asyncio
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load test environment before any app imports.
# Required fields (GIDEON_AUTH_SECRET_KEY, GIDEON_DB_URL) must be set
# before config.py is imported, because Settings() is instantiated at module level.
_ENV_TEST = Path(__file__).parent.parent / ".env.test"
load_dotenv(_ENV_TEST)

# Windows event loop policy — must be set before pytest starts
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from collections.abc import AsyncGenerator, AsyncIterator  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from shared.models.enums import Role  # noqa: E402
from sqlalchemy import create_engine, delete  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.auth import (  # noqa: E402
    create_access_token,
    get_current_user,
    hash_password,
)
from app.core.config import settings  # noqa: E402
from app.db import get_db  # noqa: E402
from app.db.models.firm import Firm  # noqa: E402
from app.db.models.matter import Matter  # noqa: E402
from app.db.models.matter_access import MatterAccess  # noqa: E402
from app.db.models.refresh_token import RefreshToken  # noqa: E402
from app.db.models.task_submission import TaskSubmission  # noqa: E402
from app.db.models.user import User  # noqa: E402
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
# FakeSession — in-memory async session stand-in for unit tests
# ---------------------------------------------------------------------------


class FakeSession:
    """Async session stand-in with configurable query results.

    Queue results with ``add_result()`` (single) or ``add_results_list()``
    (list).  Each call to ``execute()`` pops the next queued result.
    """

    def __init__(self) -> None:
        self._results: list[object] = []
        self._call_idx = 0
        self.committed = False
        self._added: list[object] = []
        self._deleted: list[object] = []

    def add_result(self, obj: object) -> None:
        self._results.append(obj)

    def add_results_list(self, objs: list[object]) -> None:
        self._results.append(objs)

    async def execute(self, stmt: object) -> MagicMock:
        result = MagicMock()
        if self._call_idx < len(self._results):
            val = self._results[self._call_idx]
            self._call_idx += 1
            if isinstance(val, list):
                result.scalars.return_value.all.return_value = val
                result.scalar_one_or_none.return_value = val[0] if val else None
                result.scalar_one.return_value = val[0] if val else None
            else:
                result.scalar_one_or_none.return_value = val
                result.scalar_one.return_value = val
                result.scalars.return_value.all.return_value = (
                    [val] if val is not None else []
                )
        else:
            result.scalar_one_or_none.return_value = None
            result.scalar_one.return_value = None
            result.scalars.return_value.all.return_value = []
        return result

    def add(self, obj: object) -> None:
        self._added.append(obj)

    async def delete(self, obj: object) -> None:
        self._deleted.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass

    async def refresh(self, obj: object) -> None:
        # Simulate server-default timestamps that PostgreSQL would populate
        now = datetime.now(UTC)
        for attr in ("created_at", "updated_at"):
            if hasattr(obj, attr) and getattr(obj, attr) is None:
                setattr(obj, attr, now)


@asynccontextmanager
async def api_client(user: User, fake: FakeSession) -> AsyncIterator[AsyncClient]:
    """Set up dependency overrides and yield an authenticated AsyncClient."""

    async def _get_db() -> AsyncGenerator[FakeSession, None]:
        yield fake

    async def _get_current_user() -> User:
        return user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


def auth_header(user: User) -> dict[str, str]:
    """Return an Authorization header dict for the given user."""
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


def fake_with_docs(docs: list, total: int | None = None) -> FakeSession:
    """Create a FakeSession pre-loaded with count + docs results for list endpoints."""
    fake = FakeSession()
    fake.add_result(total if total is not None else len(docs))  # count query
    fake.add_results_list(docs)  # main query
    return fake


# ---------------------------------------------------------------------------
# pytest-docker — integration test stack lifecycle
#
# Dev mode:  docker compose up  (uses root .env, data persists in 'gideon' DB)
# Test mode: pytest -m integration  (pytest-docker manages the stack lifecycle,
#            uses .env.test, fastapi points at 'gideon_test', volumes wiped
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
    return "gideon-test"


@pytest.fixture(scope="session")
def docker_cleanup():
    # Down with -v wipes volumes so gideon_test is reset between runs
    return "down --volumes"


def _api_ready(url: str) -> bool:
    try:
        return httpx.get(f"{url}/health", timeout=2).status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
        return False


def _redis_ready(host: str, port: int) -> bool:
    import redis as redis_lib

    try:
        r = redis_lib.Redis(host=host, port=port, socket_timeout=1)
        try:
            return r.ping()
        finally:
            r.close()
    except Exception:  # noqa: BLE001
        return False


def _minio_ready(host: str, port: int) -> bool:
    try:
        url = f"http://{host}:{port}/minio/health/live"
        return httpx.get(url, timeout=2).status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
        return False


def _tika_ready(host: str, port: int) -> bool:
    try:
        return httpx.get(f"http://{host}:{port}/tika", timeout=2).status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
        return False


def _grafana_ready(host: str, port: int) -> bool:
    try:
        return httpx.get(f"http://{host}:{port}/", timeout=2).status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
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
def redis_service(docker_ip, docker_services):
    """Ensure Redis is up and return (host, port)."""
    docker_services.wait_until_responsive(
        timeout=30.0,
        pause=0.5,
        check=lambda: _redis_ready(docker_ip, 6379),
    )
    return docker_ip, 6379


@pytest.fixture(scope="session")
def minio_service(docker_ip, docker_services):
    """Ensure MinIO is up and return (host, port)."""
    docker_services.wait_until_responsive(
        timeout=30.0,
        pause=0.5,
        check=lambda: _minio_ready(docker_ip, 9000),
    )
    return docker_ip, 9000


@pytest.fixture(scope="session")
def grafana_service(docker_ip, docker_services):
    """Wait for Grafana (otel-lgtm) to be ready and return the base URL."""
    docker_services.wait_until_responsive(
        timeout=60.0,
        pause=0.5,
        check=lambda: _grafana_ready(docker_ip, 3001),
    )
    return f"http://{docker_ip}:3001"


@pytest.fixture(scope="session")
def tika_service(docker_ip, docker_services):
    """Ensure Tika is up and return (host, port)."""
    docker_services.wait_until_responsive(
        timeout=60.0,
        pause=0.5,
        check=lambda: _tika_ready(docker_ip, 9998),
    )
    return docker_ip, 9998


_QDRANT_PORT = 6333
_OLLAMA_PORT = 11434


def _qdrant_ready(host: str, port: int) -> bool:
    try:
        return httpx.get(f"http://{host}:{port}/healthz", timeout=2).status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
        return False


def _ollama_ready(host: str, port: int) -> bool:
    try:
        return httpx.get(f"http://{host}:{port}/", timeout=2).status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
        return False


@pytest.fixture(scope="session")
def qdrant_service(docker_ip, docker_services):
    """Ensure Qdrant is up and return (host, port)."""
    docker_services.wait_until_responsive(
        timeout=60.0,
        pause=0.5,
        check=lambda: _qdrant_ready(docker_ip, _QDRANT_PORT),
    )
    return docker_ip, _QDRANT_PORT


@pytest.fixture(scope="session")
def ollama_service(docker_ip, docker_services):
    """Ensure Ollama is up and return (host, port)."""
    docker_services.wait_until_responsive(
        timeout=120.0,
        pause=1.0,
        check=lambda: _ollama_ready(docker_ip, _OLLAMA_PORT),
    )
    return docker_ip, _OLLAMA_PORT


@pytest.fixture(scope="session")
def fastapi_service(
    docker_ip,
    docker_services,
    postgres_service,
    redis_service,
    minio_service,
    tika_service,
    qdrant_service,
    ollama_service,
):
    """Start the integration compose stack and return the FastAPI base URL.

    Requires Docker to be running. Depends on all services to ensure the
    entire stack is initialized before tests run. The stack is torn down
    (with volumes) after the test session completes, leaving no residual data.
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

_SEED_ADMIN_EMAIL = "admin@example.com"
_SEED_ADMIN_PASSWORD = "integration-test-pw"  # noqa: S105


def _sync_db_url() -> str:
    """Convert async DSN to sync for direct DB access."""
    url = settings.db.url
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    return url


@pytest.fixture
def seed_admin(postgres_service):
    """Ensure an admin user exists in the test DB and yield credentials.

    If the admin bootstrap already created the user (same email from
    .env.test), reuse it and update the password. Otherwise insert a
    fresh user. Teardown only removes rows this fixture created.
    """
    from sqlalchemy import select as sa_select

    engine = create_engine(_sync_db_url())
    created_firm = False
    created_user = False

    with Session(engine) as session:
        existing = session.execute(
            sa_select(User).where(User.email == _SEED_ADMIN_EMAIL)
        ).scalar_one_or_none()

        if existing is not None:
            # Reuse bootstrap user — update password so tests can log in
            existing.hashed_password = hash_password(_SEED_ADMIN_PASSWORD)
            user_id = existing.id
            firm_id = existing.firm_id
            session.commit()
        else:
            # No bootstrap user — create from scratch
            firm_id = uuid.uuid4()
            user_id = uuid.uuid4()
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
            created_firm = True
            created_user = True

    yield {
        "user_id": user_id,
        "firm_id": firm_id,
        "email": _SEED_ADMIN_EMAIL,
        "password": _SEED_ADMIN_PASSWORD,
    }

    # Teardown — only remove rows we created (don't delete bootstrap user)
    with Session(engine) as session:
        session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
        session.execute(delete(TaskSubmission).where(TaskSubmission.user_id == user_id))
        if created_user:
            session.execute(delete(User).where(User.id == user_id))
        if created_firm:
            session.execute(delete(Firm).where(Firm.id == firm_id))
        session.commit()

    engine.dispose()


# ---------------------------------------------------------------------------
# seed_demo — integration test fixture with two users, two matters, access grants
# ---------------------------------------------------------------------------

_DEMO_PASSWORD = "DemoPassword123!"  # noqa: S105


@pytest.fixture
def seed_demo(postgres_service):
    """Seed a firm with two users, two matters, and access grants.

    - User A (attorney): access to Matter A and Matter B
    - User B (paralegal): access to Matter B only

    Yields a dict with all IDs and credentials. Cleans up after the test.
    """
    engine = create_engine(_sync_db_url())
    now = datetime.now(UTC)
    firm_id = uuid.uuid4()
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    matter_a_id = uuid.uuid4()
    matter_b_id = uuid.uuid4()

    with Session(engine) as session:
        session.add(Firm(id=firm_id, name="Demo Firm"))
        session.flush()

        session.add(
            User(
                id=user_a_id,
                firm_id=firm_id,
                email="virginia@demofirm.com",
                hashed_password=hash_password(_DEMO_PASSWORD),
                first_name="Virginia",
                last_name="Cora",
                role=Role.attorney,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            User(
                id=user_b_id,
                firm_id=firm_id,
                email="jonathan@demofirm.com",
                hashed_password=hash_password(_DEMO_PASSWORD),
                first_name="Jonathan",
                last_name="Phillips",
                role=Role.paralegal,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()

        session.add(
            Matter(
                id=matter_a_id,
                firm_id=firm_id,
                name="People v. Smith",
                client_id=uuid.uuid4(),
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Matter(
                id=matter_b_id,
                firm_id=firm_id,
                name="People v. Jones",
                client_id=uuid.uuid4(),
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()

        # User A → both matters
        session.add(
            MatterAccess(user_id=user_a_id, matter_id=matter_a_id, assigned_at=now)
        )
        session.add(
            MatterAccess(user_id=user_a_id, matter_id=matter_b_id, assigned_at=now)
        )
        # User B → Matter B only
        session.add(
            MatterAccess(user_id=user_b_id, matter_id=matter_b_id, assigned_at=now)
        )
        session.commit()

    yield {
        "firm_id": firm_id,
        "user_a": {
            "id": user_a_id,
            "email": "virginia@demofirm.com",
            "password": _DEMO_PASSWORD,
            "role": "attorney",
        },
        "user_b": {
            "id": user_b_id,
            "email": "jonathan@demofirm.com",
            "password": _DEMO_PASSWORD,
            "role": "paralegal",
        },
        "matter_a": {"id": matter_a_id, "name": "People v. Smith"},
        "matter_b": {"id": matter_b_id, "name": "People v. Jones"},
    }

    # Teardown
    with Session(engine) as session:
        session.execute(
            delete(MatterAccess).where(
                MatterAccess.matter_id.in_([matter_a_id, matter_b_id])
            )
        )
        session.execute(
            delete(RefreshToken).where(RefreshToken.user_id.in_([user_a_id, user_b_id]))
        )
        session.execute(delete(Matter).where(Matter.id.in_([matter_a_id, matter_b_id])))
        session.execute(delete(User).where(User.id.in_([user_a_id, user_b_id])))
        session.execute(delete(Firm).where(Firm.id == firm_id))
        session.commit()

    engine.dispose()
