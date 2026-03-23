"""Shared model factories for backend tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from shared.models.enums import MatterStatus, Role

from app.db.models.firm import Firm
from app.db.models.matter import Matter
from app.db.models.matter_access import MatterAccess
from app.db.models.user import User


def make_firm(**kwargs: object) -> Firm:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "Test Firm",
    }
    defaults.update(kwargs)
    return Firm(**defaults)


def make_user(**kwargs: object) -> User:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "firm_id": uuid.uuid4(),
        "email": f"{uuid.uuid4()}@example.com",
        "hashed_password": "hashed-in-test",  # noqa: S106
        "first_name": "Test",
        "last_name": "User",
        "role": Role.attorney,
        "is_active": True,
        "totp_enabled": False,
        "totp_secret": None,
        "totp_verified_at": None,
        "failed_login_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return User(**defaults)


def make_matter(**kwargs: object) -> Matter:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "firm_id": uuid.uuid4(),
        "name": "Test Matter",
        "client_id": uuid.uuid4(),
        "status": MatterStatus.open,
        "legal_hold": False,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return Matter(**defaults)


def make_matter_access(**kwargs: object) -> MatterAccess:
    defaults: dict[str, object] = {
        "user_id": uuid.uuid4(),
        "matter_id": uuid.uuid4(),
        "view_work_product": False,
        "assigned_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return MatterAccess(**defaults)
