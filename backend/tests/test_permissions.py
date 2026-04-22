"""Unit tests for backend/app/core/permissions.py — RBAC and build_permission_filter."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from shared.models.enums import Role

from app.core.constants import GLOBAL_KNOWLEDGE_MATTER_ID, is_system_matter
from app.core.permissions import (
    PermissionFilter,
    build_permission_filter,
    fetch_matter_access,
    require_matter_access,
    require_role,
)
from app.db.models.matter_access import MatterAccess
from tests.factories import make_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIRM_ID = uuid.uuid4()
_MATTER_ID = uuid.uuid4()


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
# build_permission_filter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_no_exclusions() -> None:
    user = make_user(role=Role.admin, firm_id=_FIRM_ID)
    db = _mock_db()  # should not be called

    result = await build_permission_filter(user, _MATTER_ID, db)

    assert result.firm_id == user.firm_id
    assert result.matter_ids == frozenset({_MATTER_ID, GLOBAL_KNOWLEDGE_MATTER_ID})
    assert result.excluded_classifications == frozenset()
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_attorney_excludes_jencks() -> None:
    user = make_user(role=Role.attorney, firm_id=_FIRM_ID)
    access = _make_access(user.id)
    db = _mock_db(access)

    result = await build_permission_filter(user, _MATTER_ID, db)

    assert result.excluded_classifications == frozenset({"jencks"})


@pytest.mark.asyncio
async def test_paralegal_with_work_product_excludes_jencks() -> None:
    user = make_user(role=Role.paralegal, firm_id=_FIRM_ID)
    access = _make_access(user.id, view_work_product=True)
    db = _mock_db(access)

    result = await build_permission_filter(user, _MATTER_ID, db)

    assert result.excluded_classifications == frozenset({"jencks"})


@pytest.mark.asyncio
async def test_paralegal_without_work_product_excludes_both() -> None:
    user = make_user(role=Role.paralegal, firm_id=_FIRM_ID)
    access = _make_access(user.id, view_work_product=False)
    db = _mock_db(access)

    result = await build_permission_filter(user, _MATTER_ID, db)

    assert result.excluded_classifications == frozenset({"work_product", "jencks"})


@pytest.mark.asyncio
async def test_investigator_excludes_work_product_and_jencks() -> None:
    user = make_user(role=Role.investigator, firm_id=_FIRM_ID)
    access = _make_access(user.id)
    db = _mock_db(access)

    result = await build_permission_filter(user, _MATTER_ID, db)

    assert result.excluded_classifications == frozenset({"work_product", "jencks"})


@pytest.mark.asyncio
async def test_non_admin_matter_ids_include_global_knowledge() -> None:
    """Non-admin filters should also include the global knowledge matter."""
    user = make_user(role=Role.attorney, firm_id=_FIRM_ID)
    access = _make_access(user.id)
    db = _mock_db(access)

    result = await build_permission_filter(user, _MATTER_ID, db)

    assert result.matter_ids == frozenset({_MATTER_ID, GLOBAL_KNOWLEDGE_MATTER_ID})


@pytest.mark.asyncio
async def test_system_matter_rejected_as_direct_query() -> None:
    """Passing a system matter as matter_id should raise 400."""
    user = make_user(role=Role.admin, firm_id=_FIRM_ID)
    db = _mock_db()

    with pytest.raises(HTTPException) as exc_info:
        await build_permission_filter(user, GLOBAL_KNOWLEDGE_MATTER_ID, db)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_unassigned_user_raises_404() -> None:
    user = make_user(role=Role.attorney, firm_id=_FIRM_ID)
    db = _mock_db(None)  # no access row

    with pytest.raises(HTTPException) as exc_info:
        await build_permission_filter(user, _MATTER_ID, db)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_bypasses_matter_access_check() -> None:
    user = make_user(role=Role.admin, firm_id=_FIRM_ID)
    db = _mock_db()

    result = await build_permission_filter(user, _MATTER_ID, db)

    assert isinstance(result, PermissionFilter)
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_firm_id_always_set() -> None:
    for role in Role:
        user = make_user(role=role, firm_id=_FIRM_ID)
        access = _make_access(user.id)
        db = _mock_db(access)
        result = await build_permission_filter(user, _MATTER_ID, db)
        assert result.firm_id == user.firm_id


@pytest.mark.asyncio
async def test_cross_firm_matter_returns_404() -> None:
    """A user with no MatterAccess row for another firm's matter gets 404.

    The firm-scope join in fetch_matter_access ensures that even if a
    MatterAccess row somehow existed across firms, the Matter.firm_id
    check would reject it.
    """
    other_firm_matter = uuid.uuid4()
    user = make_user(role=Role.attorney, firm_id=_FIRM_ID)
    db = _mock_db(None)  # join returns no row — firm mismatch

    with pytest.raises(HTTPException) as exc_info:
        await build_permission_filter(user, other_firm_matter, db)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# fetch_matter_access tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_returns_access_row() -> None:
    user = make_user(role=Role.attorney, firm_id=_FIRM_ID)
    access = _make_access(user.id)
    db = _mock_db(access)

    result = await fetch_matter_access(_MATTER_ID, user, db)

    assert result is access


@pytest.mark.asyncio
async def test_fetch_raises_404_when_no_row() -> None:
    user = make_user(role=Role.attorney, firm_id=_FIRM_ID)
    db = _mock_db(None)

    with pytest.raises(HTTPException) as exc_info:
        await fetch_matter_access(_MATTER_ID, user, db)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# require_role tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allowed_role_passes() -> None:
    user = make_user(role=Role.admin, firm_id=_FIRM_ID)
    dep = require_role(Role.admin)
    result = await dep(user=user)
    assert result is user


@pytest.mark.asyncio
async def test_disallowed_role_raises_403() -> None:
    user = make_user(role=Role.investigator, firm_id=_FIRM_ID)
    dep = require_role(Role.admin)

    with pytest.raises(HTTPException) as exc_info:
        await dep(user=user)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_multiple_roles_allowed() -> None:
    user = make_user(role=Role.attorney, firm_id=_FIRM_ID)
    dep = require_role(Role.admin, Role.attorney)
    result = await dep(user=user)
    assert result is user


# ---------------------------------------------------------------------------
# require_matter_access tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_matter_access_admin_bypasses() -> None:
    user = make_user(role=Role.admin, firm_id=_FIRM_ID)
    db = _mock_db()

    result = await require_matter_access(matter_id=_MATTER_ID, user=user, db=db)

    assert result is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_matter_access_assigned_user_passes() -> None:
    user = make_user(role=Role.attorney, firm_id=_FIRM_ID)
    access = _make_access(user.id)
    db = _mock_db(access)

    result = await require_matter_access(matter_id=_MATTER_ID, user=user, db=db)

    assert result is access


@pytest.mark.asyncio
async def test_matter_access_unassigned_raises_404() -> None:
    user = make_user(role=Role.attorney, firm_id=_FIRM_ID)
    db = _mock_db(None)

    with pytest.raises(HTTPException) as exc_info:
        await require_matter_access(matter_id=_MATTER_ID, user=user, db=db)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_matter_access_returns_row() -> None:
    user = make_user(role=Role.paralegal, firm_id=_FIRM_ID)
    access = _make_access(user.id, view_work_product=True)
    db = _mock_db(access)

    result = await require_matter_access(matter_id=_MATTER_ID, user=user, db=db)

    assert result is not None
    assert result.view_work_product is True


# ---------------------------------------------------------------------------
# is_system_matter tests
# ---------------------------------------------------------------------------


def test_is_system_matter_recognises_global_knowledge() -> None:
    assert is_system_matter(GLOBAL_KNOWLEDGE_MATTER_ID) is True


def test_is_system_matter_rejects_regular_uuid() -> None:
    assert is_system_matter(uuid.uuid4()) is False


# ---------------------------------------------------------------------------
# Backwards-compatibility alias tests
# ---------------------------------------------------------------------------


def test_backwards_compat_alias_exists() -> None:
    """Confirm build_qdrant_filter alias is still importable."""
    # This is the most critical test — if the alias is missing,
    # any external code still using the old name will fail.
    from app.core.permissions import build_qdrant_filter as alias_func

    assert callable(alias_func)


@pytest.mark.asyncio
async def test_backwards_compat_alias_emits_deprecation_warning() -> None:
    """Confirm build_qdrant_filter emits a deprecation warning."""
    import warnings

    from app.core.permissions import build_qdrant_filter

    user = make_user(role=Role.admin, firm_id=_FIRM_ID)
    db = _mock_db()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        await build_qdrant_filter(user, _MATTER_ID, db)

        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "build_qdrant_filter is deprecated" in str(w[0].message)
