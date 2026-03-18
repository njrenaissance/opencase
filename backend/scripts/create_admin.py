#!/usr/bin/env python3
"""Bootstrap script — create the first firm and admin user.

Run once during initial deployment:

    python scripts/create_admin.py \\
        --email admin@corafirm.com \\
        --password 'S3cure!Pass' \\
        --first-name Virginia \\
        --last-name Cora \\
        --firm-name 'Cora Firm'

Requires OPENCASE_DB_URL to be set (or .env to be present).
Uses a *synchronous* engine — no async runtime needed.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# We only need the config layer and the auth hash function.
# Avoid importing the async engine (app.db.session) which would try to
# create an asyncpg connection pool at import time.
# ---------------------------------------------------------------------------
from app.core.auth import hash_password
from app.core.config import settings
from app.db.models.firm import Firm
from app.db.models.user import Role, User


def _sync_url() -> str:
    """Convert the async DSN to a sync one (asyncpg → psycopg2)."""
    url = settings.db.url
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the initial admin user.")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--first-name", required=True, help="First name")
    parser.add_argument("--last-name", required=True, help="Last name")
    parser.add_argument("--firm-name", required=True, help="Firm name")
    args = parser.parse_args()

    engine = create_engine(_sync_url())

    with Session(engine) as session:
        # Verify the database is reachable.
        session.execute(text("SELECT 1"))

        # Create firm if it doesn't exist.
        firm = session.execute(
            select(Firm).where(Firm.name == args.firm_name)
        ).scalar_one_or_none()

        if firm is None:
            firm = Firm(id=uuid.uuid4(), name=args.firm_name)
            session.add(firm)
            session.flush()
            print(f"Created firm: {args.firm_name} (id={firm.id})")  # noqa: T201
        else:
            print(f"Firm already exists: {args.firm_name} (id={firm.id})")  # noqa: T201

        # Check if the user already exists.
        existing = session.execute(
            select(User).where(User.email == args.email, User.firm_id == firm.id)
        ).scalar_one_or_none()

        if existing is not None:
            print(f"Admin user already exists: {args.email} (id={existing.id})")  # noqa: T201
            sys.exit(0)

        user = User(
            id=uuid.uuid4(),
            firm_id=firm.id,
            email=args.email,
            hashed_password=hash_password(args.password),
            first_name=args.first_name,
            last_name=args.last_name,
            role=Role.admin,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(user)
        session.commit()
        print(f"Created admin user: {args.email} (id={user.id})")  # noqa: T201
        print("Log in at POST /auth/login with email + password.")  # noqa: T201


if __name__ == "__main__":
    main()
