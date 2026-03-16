"""Integration tests for database schema constraints.

These tests require a running PostgreSQL instance (OPENCASE_DB_URL in .env.test).
Run with: pytest -m integration

Each test runs inside a transaction that is rolled back on completion,
so tests are isolated and leave no residual data.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.models import Firm, Matter, MatterAccess, User
from app.db.models.matter import MatterStatus
from app.db.models.user import Role

# All tests share the session-scoped async engine fixture, so they must run
# in the same event loop — loop_scope="session" ensures that.
pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


# ---------------------------------------------------------------------------
# Session-scoped engine: create schema once, drop after all tests complete.
# Uses Base.metadata rather than alembic so tests are self-contained.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def engine(postgres_service):  # noqa: ARG001 — ensures pytest-docker starts postgres first
    engine = create_async_engine(settings.db.url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """Each test gets a transaction that is always rolled back."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess, sess.begin():
        yield sess
        await sess.rollback()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_firm(**kwargs) -> Firm:
    return Firm(id=uuid.uuid4(), name="Test Firm", **kwargs)


def make_user(firm_id: uuid.UUID, **kwargs) -> User:
    return User(
        id=uuid.uuid4(),
        firm_id=firm_id,
        email=kwargs.pop("email", f"{uuid.uuid4()}@example.com"),
        hashed_password="hashed-in-test",  # noqa: S106
        first_name="Jane",
        last_name="Doe",
        role=Role.attorney,
        **kwargs,
    )


def make_matter(firm_id: uuid.UUID, **kwargs) -> Matter:
    return Matter(
        id=uuid.uuid4(),
        firm_id=firm_id,
        name="Test Matter",
        client_id=uuid.uuid4(),
        status=MatterStatus.open,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Firm
# ---------------------------------------------------------------------------


async def test_firm_insert(session):
    firm = make_firm()
    session.add(firm)
    await session.flush()
    result = await session.get(Firm, firm.id)
    assert result is not None
    assert result.name == "Test Firm"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


async def test_user_insert(session):
    firm = make_firm()
    session.add(firm)
    await session.flush()

    user = make_user(firm.id)
    session.add(user)
    await session.flush()

    result = await session.get(User, user.id)
    assert result.email == user.email
    assert result.first_name == "Jane"
    assert result.last_name == "Doe"


async def test_user_invalid_firm_fk_raises(session):
    user = make_user(uuid.uuid4())  # non-existent firm_id
    session.add(user)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_user_duplicate_email_same_firm_raises(session):
    firm = make_firm()
    session.add(firm)
    await session.flush()

    email = "duplicate@example.com"
    session.add(make_user(firm.id, email=email))
    session.add(make_user(firm.id, email=email))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_user_same_email_different_firms_allowed(session):
    firm_a = make_firm()
    firm_b = Firm(id=uuid.uuid4(), name="Firm B")
    session.add_all([firm_a, firm_b])
    await session.flush()

    email = "shared@example.com"
    session.add(make_user(firm_a.id, email=email))
    session.add(make_user(firm_b.id, email=email))
    await session.flush()  # must not raise


async def test_user_cascade_delete_with_firm(session):
    firm = make_firm()
    session.add(firm)
    await session.flush()

    user = make_user(firm.id)
    session.add(user)
    await session.flush()

    await session.delete(firm)
    await session.flush()

    # Use select() to bypass the identity map and confirm the DB row is gone
    row = await session.execute(select(User).where(User.id == user.id))
    assert row.scalar_one_or_none() is None  # cascaded by DB-level ON DELETE CASCADE


# ---------------------------------------------------------------------------
# Matter
# ---------------------------------------------------------------------------


async def test_matter_insert(session):
    firm = make_firm()
    session.add(firm)
    await session.flush()

    matter = make_matter(firm.id)
    session.add(matter)
    await session.flush()

    result = await session.get(Matter, matter.id)
    assert result.status == MatterStatus.open
    assert result.legal_hold is False


async def test_matter_invalid_firm_fk_raises(session):
    matter = make_matter(uuid.uuid4())
    session.add(matter)
    with pytest.raises(IntegrityError):
        await session.flush()


# ---------------------------------------------------------------------------
# MatterAccess
# ---------------------------------------------------------------------------


async def test_matter_access_insert(session):
    firm = make_firm()
    session.add(firm)
    await session.flush()

    user = make_user(firm.id)
    matter = make_matter(firm.id)
    session.add_all([user, matter])
    await session.flush()

    access = MatterAccess(user_id=user.id, matter_id=matter.id)
    session.add(access)
    await session.flush()

    result = await session.get(MatterAccess, (user.id, matter.id))
    assert result is not None
    assert result.view_work_product is False


async def test_matter_access_duplicate_pk_raises(session):
    firm = make_firm()
    session.add(firm)
    await session.flush()

    user = make_user(firm.id)
    matter = make_matter(firm.id)
    session.add_all([user, matter])
    await session.flush()

    session.add(MatterAccess(user_id=user.id, matter_id=matter.id))
    session.add(MatterAccess(user_id=user.id, matter_id=matter.id))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_matter_access_cascade_delete_with_user(session):
    firm = make_firm()
    session.add(firm)
    await session.flush()

    user = make_user(firm.id)
    matter = make_matter(firm.id)
    session.add_all([user, matter])
    await session.flush()

    session.add(MatterAccess(user_id=user.id, matter_id=matter.id))
    await session.flush()

    await session.delete(user)
    await session.flush()

    result = await session.get(MatterAccess, (user.id, matter.id))
    assert result is None  # cascaded
