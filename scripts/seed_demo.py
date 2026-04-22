#!/usr/bin/env python3
"""Seed demo data via the API — firm, users, matters, access grants.

Creates:
    - User A (attorney): demo attorney — access to Matter A and Matter B
    - User B (paralegal): demo paralegal — access to Matter B only
    - Matter A: People v. Smith
    - Matter B: People v. Jones

Idempotent — safe to run multiple times.  Skips existing records.
Requires the dev stack to be running.

Usage (from repo root):
    uv run python scripts/seed_demo.py
    uv run python scripts/seed_demo.py --env .env
"""

from __future__ import annotations

import argparse
import sys
import uuid

import dotenv
from gideon import Client
from gideon.exceptions import GideonError, ValidationError

BASE_URL = "http://127.0.0.1:8000"
HTTP_CONFLICT = 409
DEMO_PASSWORD = "DemoPassword123!"  # noqa: S105


def _create_user(
    client: Client,
    email: str,
    first_name: str,
    last_name: str,
    role: str,
) -> str:
    """Create a user, return user_id.  Skip if already exists."""
    try:
        user = client.create_user(
            email=email,
            password=DEMO_PASSWORD,
            first_name=first_name,
            last_name=last_name,
            role=role,
        )
        print(f"  Created user: {first_name} {last_name} <{email}> ({role})")  # noqa: T201
        return str(user.id)
    except (GideonError, ValidationError) as exc:
        if "already" in str(exc).lower() or getattr(exc, "status_code", 0) == HTTP_CONFLICT:
            # User exists — find them
            users = client.list_users()
            for u in users:
                if u.email == email:
                    print(f"  User already exists: {email} ({u.id})")  # noqa: T201
                    return str(u.id)
        raise


def _create_matter(client: Client, name: str) -> str:
    """Create a matter, return matter_id.  Skip if already exists."""
    matters = client.list_matters()
    for m in matters:
        if m.name == name:
            print(f"  Matter already exists: {name} ({m.id})")  # noqa: T201
            return str(m.id)

    matter = client.create_matter(name=name, client_id=str(uuid.uuid4()))
    print(f"  Created matter: {name} ({matter.id})")  # noqa: T201
    return str(matter.id)


def _grant_access(
    client: Client,
    matter_id: str,
    user_id: str,
    label: str,
) -> None:
    """Grant matter access.  Skip if already granted."""
    try:
        existing = client.list_matter_access(matter_id)
        for a in existing:
            if str(a.user_id) == user_id:
                print(f"  Access already exists: {label}")  # noqa: T201
                return
        client.grant_matter_access(matter_id, user_id=user_id)
        print(f"  Granted access: {label}")  # noqa: T201
    except GideonError as exc:
        print(f"  Warning: {label}: {exc}")  # noqa: T201


def main(config_file: str) -> None:
    admin_email = dotenv.get_key(config_file, "GIDEON_ADMIN_EMAIL")
    admin_password = dotenv.get_key(config_file, "GIDEON_ADMIN_PASSWORD")

    if not admin_email or not admin_password:
        print("ERROR: GIDEON_ADMIN_EMAIL / GIDEON_ADMIN_PASSWORD not set in .env")  # noqa: T201
        sys.exit(1)

    with Client(base_url=BASE_URL) as client:
        print(f"Logging in as {admin_email}")  # noqa: T201
        client.login(email=admin_email, password=admin_password)

        # Users
        print("\nCreating users...")  # noqa: T201
        user_a = _create_user(client, "virginia@corafirm.com", "Virginia", "Cora", "attorney")
        user_b = _create_user(client, "jonathan@corafirm.com", "Jonathan", "Phillips", "paralegal")

        # Matters
        print("\nCreating matters...")  # noqa: T201
        matter_a = _create_matter(client, "People v. Smith")
        matter_b = _create_matter(client, "People v. Jones")

        # Access grants
        print("\nGranting access...")  # noqa: T201
        _grant_access(client, matter_a, user_a, "Virginia -> People v. Smith")
        _grant_access(client, matter_b, user_a, "Virginia -> People v. Jones")
        _grant_access(client, matter_b, user_b, "Jonathan -> People v. Jones")

        client.logout()
        print("\nDemo seed complete.")  # noqa: T201


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo data via the API.")
    parser.add_argument(
        "--env",
        default=".env",
        help="Path to .env file (default: .env)",
    )
    args = parser.parse_args()
    main(config_file=args.env)
