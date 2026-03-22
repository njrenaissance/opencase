#!/usr/bin/env python3
"""Bootstrap script — create the first firm and admin user.

Reads configuration from environment variables (preferred in Docker)
or CLI arguments (for manual use):

    # Via environment (Docker Compose):
    OPENCASE_ADMIN_EMAIL=admin@corafirm.com
    OPENCASE_ADMIN_PASSWORD=S3cure!Pass
    OPENCASE_ADMIN_FIRST_NAME=Virginia
    OPENCASE_ADMIN_LAST_NAME=Cora
    OPENCASE_ADMIN_FIRM_NAME="Cora Firm"

    # Via CLI:
    python -m scripts.create_admin \\
        --email admin@corafirm.com \\
        --password 'S3cure!Pass' \\
        --first-name Virginia \\
        --last-name Cora \\
        --firm-name 'Cora Firm'

Idempotent — safe to run on every container startup.
Requires OPENCASE_DB_URL to be set (or .env to be present).
Uses asyncio + asyncpg (the only PostgreSQL driver installed).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# We only need the config layer and the auth hash function.
# Avoid importing app.db.session which creates a module-level engine.
# ---------------------------------------------------------------------------
from app.core.auth import hash_password
from app.core.config import settings
from app.db.models.firm import Firm
from app.db.models.user import Role, User


async def _seed(  # noqa: PLR0913
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    firm_name: str,
    session: AsyncSession | None = None,
) -> None:
    """Create the initial firm and admin user.

    When called from the FastAPI lifespan hook, *session* is provided by the
    caller (reusing the app's connection pool).  When called from the CLI
    entry-point no session exists yet, so we create a throwaway engine.
    """
    if session is not None:
        await _seed_with_session(
            session, email, password, first_name, last_name, firm_name
        )
        return

    # CLI path — standalone engine (no app pool available).
    engine = create_async_engine(settings.db.url)
    try:
        async_session = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as sess:
            await _seed_with_session(
                sess, email, password, first_name, last_name, firm_name
            )
    finally:
        await engine.dispose()


async def _seed_with_session(  # noqa: PLR0913
    session: AsyncSession,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    firm_name: str,
) -> None:
    """Core seed logic operating on an existing session."""
    # Verify the database is reachable.
    await session.execute(text("SELECT 1"))

    # Create firm if it doesn't exist.
    result = await session.execute(select(Firm).where(Firm.name == firm_name))
    firm = result.scalar_one_or_none()

    if firm is None:
        firm = Firm(id=uuid.uuid4(), name=firm_name)
        session.add(firm)
        await session.flush()
        print(f"Created firm: {firm_name} (id={firm.id})")  # noqa: T201
    else:
        print(f"Firm already exists: {firm_name} (id={firm.id})")  # noqa: T201

    # Check if the user already exists.
    result = await session.execute(
        select(User).where(User.email == email, User.firm_id == firm.id)
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        print(f"Admin user already exists: {email} (id={existing.id})")  # noqa: T201
        return

    user = User(
        id=uuid.uuid4(),
        firm_id=firm.id,
        email=email,
        hashed_password=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=Role.admin,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    await session.commit()
    print(f"Created admin user: {email} (id={user.id})")  # noqa: T201


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the initial admin user.")
    parser.add_argument("--email", default=None, help="Admin email address")
    parser.add_argument("--password", default=None, help="Admin password")
    parser.add_argument("--first-name", default=None, help="First name")
    parser.add_argument("--last-name", default=None, help="Last name")
    parser.add_argument("--firm-name", default=None, help="Firm name")
    args = parser.parse_args()

    # Environment variables take precedence over CLI arguments.
    email = os.environ.get("OPENCASE_ADMIN_EMAIL") or args.email
    password = os.environ.get("OPENCASE_ADMIN_PASSWORD") or args.password
    first_name = os.environ.get("OPENCASE_ADMIN_FIRST_NAME") or args.first_name
    last_name = os.environ.get("OPENCASE_ADMIN_LAST_NAME") or args.last_name
    firm_name = os.environ.get("OPENCASE_ADMIN_FIRM_NAME") or args.firm_name

    missing = []
    if not email:
        missing.append("OPENCASE_ADMIN_EMAIL / --email")
    if not password:
        missing.append("OPENCASE_ADMIN_PASSWORD / --password")
    if not first_name:
        missing.append("OPENCASE_ADMIN_FIRST_NAME / --first-name")
    if not last_name:
        missing.append("OPENCASE_ADMIN_LAST_NAME / --last-name")
    if not firm_name:
        missing.append("OPENCASE_ADMIN_FIRM_NAME / --firm-name")

    if missing:
        print(f"Missing required values: {', '.join(missing)}")  # noqa: T201
        sys.exit(1)

    asyncio.run(_seed(email, password, first_name, last_name, firm_name))


if __name__ == "__main__":
    main()
