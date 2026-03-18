"""Unit tests for backend/app/core/permissions.py — RBAC and build_qdrant_filter."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.permissions import (
    PermissionFilter,
    _fetch_matter_access,
    build_qdrant_filter,
    require_matter_access,
    require_role,
)
from app.db.models.matter_access import MatterAccess
from app.db.models.user import Role, User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIRM_ID = uuid.uuid4()
_MATTER_ID = uuid.uuid4()


def _make_user(role: Role = Role.attorney, **overrides: object) -> User:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "firm_id": _FIRM_ID,
        "email": "test@example.com",
        "hashed_password": "x",
        "first_name": "Test",
        "last_name": "User",
        "role": role,
        "is_active": True,
        "totp_enabled": False,
        "totp_secret": None,
        "totp_verified_at": None,
        "failed_login_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return User(**defaults)


def _make_access(
    user_id: uuid.UUID,
    matter_id: uuid.UUID = _MATTER_ID,
    view_work_product: bool = False,
) -> MatterAccess:
    return MatterAccess(
        user_id=user_id,
        matter_id=matter_id,
        view_work_product=view_work_product,
        assigned_at=datetime.now(UTC),
    )


def _mock_db(return_value: object = None) -> AsyncMock:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    db = AsyncMock()
    db.execute.return_value = mock_result
    return db


# ---------------------------------------------------------------------------
# build_qdrant_filter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_no_exclusions() -> None:
    user = _make_user(Role.admin)
    db = _mock_db()  # should not be called

    result = await build_qdrant_filter(user, _MATTER_ID, db)

    assert result.firm_id == user.firm_id
    assert result.matter_id == _MATTER_ID
    assert result.excluded_classifications == frozenset()
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_attorney_excludes_jencks() -> None:
    user = _make_user(Role.attorney)
    access = _make_access(user.id)
    db = _mock_db(access)

    result = await build_qdrant_filter(user, _MATTER_ID, db)

    assert result.excluded_classifications == frozenset({"jencks"})


@pytest.mark.asyncio
async def test_paralegal_with_work_product_excludes_jencks() -> None:
    user = _make_user(Role.paralegal)
    access = _make_access(user.id, view_work_product=True)
    db = _mock_db(access)

    result = await build_qdrant_filter(user, _MATTER_ID, db)

    assert result.excluded_classifications == frozenset({"jencks"})


@pytest.mark.asyncio
async def test_paralegal_without_work_product_excludes_both() -> None:
    user = _make_user(Role.paralegal)
    access = _make_access(user.id, view_work_product=False)
    db = _mock_db(access)

    result = await build_qdrant_filter(user, _MATTER_ID, db)

    assert result.excluded_classifications == frozenset({"work_product", "jencks"})


@pytest.mark.asyncio
async def test_investigator_excludes_work_product_and_jencks() -> None:
    user = _make_user(Role.investigator)
    access = _make_access(user.id)
    db = _mock_db(access)

    result = await build_qdrant_filter(user, _MATTER_ID, db)

    assert result.excluded_classifications == frozenset({"work_product", "jencks"})


@pytest.mark.asyncio
async def test_unassigned_user_raises_404() -> None:
    user = _make_user(Role.attorney)
    db = _mock_db(None)  # no access row

    with pytest.raises(HTTPException) as exc_info:
        await build_qdrant_filter(user, _MATTER_ID, db)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_bypasses_matter_access_check() -> None:
    user = _make_user(Role.admin)
    db = _mock_db()

    result = await build_qdrant_filter(user, _MATTER_ID, db)

    assert isinstance(result, PermissionFilter)
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_firm_id_always_set() -> None:
    for role in Role:
        user = _make_user(role)
        access = _make_access(user.id)
        db = _mock_db(access)
        result = await build_qdrant_filter(user, _MATTER_ID, db)
        assert result.firm_id == user.firm_id


@pytest.mark.asyncio
async def test_cross_firm_matter_returns_404() -> None:
    """A user with no MatterAccess row for another firm's matter gets 404.

    The firm-scope join in _fetch_matter_access ensures that even if a
    MatterAccess row somehow existed across firms, the Matter.firm_id
    check would reject it.
    """
    other_firm_matter = uuid.uuid4()
    user = _make_user(Role.attorney)
    db = _mock_db(None)  # join returns no row — firm mismatch

    with pytest.raises(HTTPException) as exc_info:
        await build_qdrant_filter(user, other_firm_matter, db)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# _fetch_matter_access tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_returns_access_row() -> None:
    user = _make_user(Role.attorney)
    access = _make_access(user.id)
    db = _mock_db(access)

    result = await _fetch_matter_access(_MATTER_ID, user, db)

    assert result is access


@pytest.mark.asyncio
async def test_fetch_raises_404_when_no_row() -> None:
    user = _make_user(Role.attorney)
    db = _mock_db(None)

    with pytest.raises(HTTPException) as exc_info:
        await _fetch_matter_access(_MATTER_ID, user, db)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# require_role tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allowed_role_passes() -> None:
    user = _make_user(Role.admin)
    dep = require_role(Role.admin)
    result = await dep(user=user)
    assert result is user


@pytest.mark.asyncio
async def test_disallowed_role_raises_403() -> None:
    user = _make_user(Role.investigator)
    dep = require_role(Role.admin)

    with pytest.raises(HTTPException) as exc_info:
        await dep(user=user)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_multiple_roles_allowed() -> None:
    user = _make_user(Role.attorney)
    dep = require_role(Role.admin, Role.attorney)
    result = await dep(user=user)
    assert result is user


# ---------------------------------------------------------------------------
# require_matter_access tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_matter_access_admin_bypasses() -> None:
    user = _make_user(Role.admin)
    db = _mock_db()

    result = await require_matter_access(matter_id=_MATTER_ID, user=user, db=db)

    assert result is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_matter_access_assigned_user_passes() -> None:
    user = _make_user(Role.attorney)
    access = _make_access(user.id)
    db = _mock_db(access)

    result = await require_matter_access(matter_id=_MATTER_ID, user=user, db=db)

    assert result is access


@pytest.mark.asyncio
async def test_matter_access_unassigned_raises_404() -> None:
    user = _make_user(Role.attorney)
    db = _mock_db(None)

    with pytest.raises(HTTPException) as exc_info:
        await require_matter_access(matter_id=_MATTER_ID, user=user, db=db)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_matter_access_returns_row() -> None:
    user = _make_user(Role.paralegal)
    access = _make_access(user.id, view_work_product=True)
    db = _mock_db(access)

    result = await require_matter_access(matter_id=_MATTER_ID, user=user, db=db)

    assert result is not None
    assert result.view_work_product is True
