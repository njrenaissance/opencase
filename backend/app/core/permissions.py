"""RBAC middleware — role enforcement and vector query access control.

build_qdrant_filter() is the most security-critical function in the
codebase. It is called on every vector query without exception, never
bypassed, and never accepts client-supplied filter parameters.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status
from opentelemetry import trace
from shared.models.enums import Classification, Role
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.constants import GLOBAL_KNOWLEDGE_MATTER_ID
from app.core.metrics import access_denied
from app.db import get_db
from app.db.models.matter import Matter
from app.db.models.matter_access import MatterAccess
from app.db.models.user import User

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


# ---------------------------------------------------------------------------
# PermissionFilter — abstract filter returned by build_qdrant_filter()
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PermissionFilter:
    """Qdrant-agnostic access control filter.

    Converted to ``qdrant_client.models.Filter`` in the RAG layer
    (Feature 5). Keeping it abstract here makes it testable without
    a Qdrant dependency.

    ``matter_ids`` always includes both the requested matter and the
    global knowledge matter so that shared legal references are
    returned alongside case-specific results.
    """

    firm_id: uuid.UUID
    matter_ids: frozenset[uuid.UUID]
    excluded_classifications: frozenset[str]


# ---------------------------------------------------------------------------
# fetch_matter_access — shared helper used by build_qdrant_filter,
# require_matter_access, and the document router. Separated from FastAPI DI
# so callers can invoke it directly without going through Depends().
# ---------------------------------------------------------------------------


async def fetch_matter_access(
    matter_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> MatterAccess:
    """Look up the MatterAccess row with an explicit firm-scope join.

    Validates that the matter belongs to the user's firm *and* that
    the user has an access grant for it. Returns the ``MatterAccess``
    row on success.

    Raises:
        HTTPException(404): If the matter is not in the user's firm or
            the user has no access grant.
    """
    result = await db.execute(
        select(MatterAccess)
        .join(Matter, Matter.id == MatterAccess.matter_id)
        .where(
            MatterAccess.user_id == user.id,
            MatterAccess.matter_id == matter_id,
            Matter.firm_id == user.firm_id,
        )
    )
    access_row = result.scalar_one_or_none()

    if access_row is None:
        access_denied.add(1, {"reason": "matter", "role": user.role.value})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return access_row


# ---------------------------------------------------------------------------
# build_qdrant_filter() — called on every vector query
# ---------------------------------------------------------------------------


async def build_qdrant_filter(
    user: User,
    matter_id: uuid.UUID,
    db: AsyncSession,
) -> PermissionFilter:
    """Build an access-control filter for a vector query.

    This function is called on **every** vector query without exception.
    It never accepts client-supplied filter parameters and is never
    bypassed.

    Returns a ``PermissionFilter`` describing what the user is allowed
    to see for the given matter.

    Raises:
        HTTPException(404): If the user has no access to the matter.
    """
    # OpenTelemetry: synchronous context manager around async body is the
    # standard pattern for opentelemetry-api (Python). The SDK propagates
    # the span correctly across await boundaries via contextvars.
    with tracer.start_as_current_span(
        "permissions.build_qdrant_filter",
        attributes={"user.id": str(user.id), "matter.id": str(matter_id)},
    ):
        excluded: set[str] = set()

        # Admin: full access, no MatterAccess check required.
        if user.role == Role.admin:
            return PermissionFilter(
                firm_id=user.firm_id,
                matter_ids=frozenset({matter_id, GLOBAL_KNOWLEDGE_MATTER_ID}),
                excluded_classifications=frozenset(excluded),
            )

        # Non-admin: verify MatterAccess row exists with firm-scope join.
        access_row = await fetch_matter_access(matter_id, user, db)

        # Jencks gating — excluded for all non-Admin until Feature 11.1
        # adds witness testimony tracking.
        excluded.add(Classification.jencks)

        # Work product gating.
        if user.role == Role.investigator or (
            user.role == Role.paralegal and not access_row.view_work_product
        ):
            excluded.add(Classification.work_product)
        # Attorney and Paralegal-with-grant: work_product allowed.

        return PermissionFilter(
            firm_id=user.firm_id,
            matter_ids=frozenset({matter_id, GLOBAL_KNOWLEDGE_MATTER_ID}),
            excluded_classifications=frozenset(excluded),
        )


# ---------------------------------------------------------------------------
# require_role — dependency factory for role-based endpoint gating
# ---------------------------------------------------------------------------


def require_role(
    *roles: Role,
) -> Callable[..., Any]:
    """Return a FastAPI dependency that enforces role membership.

    Usage::

        @router.get("/admin-only")
        async def admin_endpoint(
            user: User = Depends(require_role(Role.admin)),
        ):
            ...
    """

    async def _check(
        user: User = Depends(get_current_user),  # noqa: B008
    ) -> User:
        with tracer.start_as_current_span(
            "permissions.check_role",
            attributes={"user.role": user.role.value},
        ):
            if user.role not in roles:
                access_denied.add(1, {"reason": "role", "role": user.role.value})
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )
            return user

    return _check


# ---------------------------------------------------------------------------
# require_matter_access — FastAPI dependency for matter-scoped endpoints
# ---------------------------------------------------------------------------


async def require_matter_access(
    matter_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MatterAccess | None:
    """Verify the user has access to the given matter.

    Thin FastAPI dependency wrapper around ``fetch_matter_access``.

    Returns:
        ``MatterAccess`` for non-admin users (always — a missing row
        raises 404, never returns ``None``).
        ``None`` only for Admin users, who bypass the MatterAccess
        check entirely (single-tenant, full-firm access).

    Raises:
        HTTPException(404): If a non-admin user has no access.
    """
    with tracer.start_as_current_span(
        "permissions.check_matter_access",
        attributes={"user.id": str(user.id), "matter.id": str(matter_id)},
    ):
        # Admin bypasses MatterAccess check — single-tenant deployment
        # means admin always belongs to the only firm.
        if user.role == Role.admin:
            return None

        return await fetch_matter_access(matter_id, user, db)
