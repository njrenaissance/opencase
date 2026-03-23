#!/usr/bin/env python3
"""Seed demo data — firm, two users, two matters, access grants.

Creates:
    - Cora Firm
    - User A (attorney): Virginia Cora — access to Matter A and Matter B
    - User B (paralegal): Jonathan Phillips — access to Matter B only
    - Matter A: People v. Smith
    - Matter B: People v. Jones

Idempotent — safe to run multiple times. Skips existing records.
Requires OPENCASE_DB_URL to be set (or .env to be present).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from shared.models.enums import MatterStatus, Role
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import hash_password
from app.core.config import settings
from app.db.models.firm import Firm
from app.db.models.matter import Matter
from app.db.models.matter_access import MatterAccess
from app.db.models.user import User

# ---------------------------------------------------------------------------
# Demo data — deterministic UUIDs for idempotency
# ---------------------------------------------------------------------------

FIRM_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
USER_A_ID = uuid.UUID("00000000-0000-4000-8000-00000000000a")
USER_B_ID = uuid.UUID("00000000-0000-4000-8000-00000000000b")
MATTER_A_ID = uuid.UUID("00000000-0000-4000-8000-0000000000a0")
MATTER_B_ID = uuid.UUID("00000000-0000-4000-8000-0000000000b0")

PASSWORD = "DemoPassword123!"  # noqa: S105


async def _seed(session: AsyncSession) -> None:
    await session.execute(text("SELECT 1"))
    now = datetime.now(UTC)

    # -- Firm ----------------------------------------------------------------
    firm = (
        await session.execute(select(Firm).where(Firm.id == FIRM_ID))
    ).scalar_one_or_none()

    if firm is None:
        firm = Firm(id=FIRM_ID, name="Cora Firm")
        session.add(firm)
        await session.flush()
        print(f"Created firm: Cora Firm (id={FIRM_ID})")  # noqa: T201
    else:
        print(f"Firm already exists: Cora Firm (id={FIRM_ID})")  # noqa: T201

    # -- Users ---------------------------------------------------------------
    for user_id, email, first, last, role in [
        (USER_A_ID, "virginia@corafirm.com", "Virginia", "Cora", Role.attorney),
        (USER_B_ID, "jonathan@corafirm.com", "Jonathan", "Phillips", Role.paralegal),
    ]:
        existing = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()

        if existing is not None:
            print(f"User already exists: {email} (id={user_id})")  # noqa: T201
            continue

        session.add(
            User(
                id=user_id,
                firm_id=FIRM_ID,
                email=email,
                hashed_password=hash_password(PASSWORD),
                first_name=first,
                last_name=last,
                role=role,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        print(f"Created user: {first} {last} <{email}> ({role})")  # noqa: T201

    await session.flush()

    # -- Matters -------------------------------------------------------------
    for matter_id, name in [
        (MATTER_A_ID, "People v. Smith"),
        (MATTER_B_ID, "People v. Jones"),
    ]:
        existing = (
            await session.execute(select(Matter).where(Matter.id == matter_id))
        ).scalar_one_or_none()

        if existing is not None:
            print(f"Matter already exists: {name} (id={matter_id})")  # noqa: T201
            continue

        session.add(
            Matter(
                id=matter_id,
                firm_id=FIRM_ID,
                name=name,
                client_id=uuid.uuid4(),
                status=MatterStatus.open,
                legal_hold=False,
                created_at=now,
                updated_at=now,
            )
        )
        print(f"Created matter: {name}")  # noqa: T201

    await session.flush()

    # -- Matter Access -------------------------------------------------------
    # User A (Virginia) → Matter A + Matter B
    # User B (David)    → Matter B only
    grants = [
        (USER_A_ID, MATTER_A_ID, "Virginia → People v. Smith"),
        (USER_A_ID, MATTER_B_ID, "Virginia → People v. Jones"),
        (USER_B_ID, MATTER_B_ID, "Jonathan → People v. Jones"),
    ]

    for user_id, matter_id, label in grants:
        existing = (
            await session.execute(
                select(MatterAccess).where(
                    MatterAccess.user_id == user_id,
                    MatterAccess.matter_id == matter_id,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            print(f"Access already exists: {label}")  # noqa: T201
            continue

        session.add(
            MatterAccess(
                user_id=user_id,
                matter_id=matter_id,
                view_work_product=False,
                assigned_at=now,
            )
        )
        print(f"Granted access: {label}")  # noqa: T201

    await session.commit()
    print("\nDemo seed complete.")  # noqa: T201


async def main() -> None:
    engine = create_async_engine(settings.db.url)
    try:
        async_session = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            await _seed(session)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
