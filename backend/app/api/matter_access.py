"""MatterAccess router — Admin-only grant and revoke of matter access."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from opentelemetry import trace
from shared.models.base import MessageResponse
from shared.models.enums import Role
from shared.models.matter_access import GrantAccessRequest, MatterAccessResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.helpers import commit_or_conflict, verify_in_firm
from app.core.metrics import matter_access_granted, matter_access_revoked
from app.core.permissions import require_role
from app.db import get_db
from app.db.models.matter import Matter
from app.db.models.matter_access import MatterAccess
from app.db.models.user import User

tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/matters", tags=["matter-access"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _access_to_response(row: MatterAccess) -> MatterAccessResponse:
    return MatterAccessResponse(
        user_id=row.user_id,
        matter_id=row.matter_id,
        view_work_product=row.view_work_product,
        assigned_at=row.assigned_at,
    )


# ---------------------------------------------------------------------------
# GET /matters/{matter_id}/access
# ---------------------------------------------------------------------------


@router.get(
    "/{matter_id}/access",
    response_model=list[MatterAccessResponse],
)
async def list_matter_access(
    matter_id: uuid.UUID,
    user: User = Depends(require_role(Role.admin)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[MatterAccessResponse]:
    with tracer.start_as_current_span(
        "matter_access.list",
        attributes={"user.id": str(user.id), "matter.id": str(matter_id)},
    ):
        await verify_in_firm(matter_id, user.firm_id, db, Matter)

        result = await db.execute(
            select(MatterAccess).where(MatterAccess.matter_id == matter_id)
        )
        return [_access_to_response(row) for row in result.scalars().all()]


# ---------------------------------------------------------------------------
# POST /matters/{matter_id}/access
# ---------------------------------------------------------------------------


@router.post(
    "/{matter_id}/access",
    response_model=MatterAccessResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {}, 409: {}},
)
async def grant_matter_access(
    matter_id: uuid.UUID,
    body: GrantAccessRequest,
    user: User = Depends(require_role(Role.admin)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MatterAccessResponse:
    with tracer.start_as_current_span(
        "matter_access.grant",
        attributes={"user.id": str(user.id), "matter.id": str(matter_id)},
    ):
        await verify_in_firm(matter_id, user.firm_id, db, Matter)
        await verify_in_firm(
            body.user_id, user.firm_id, db, User, "User not found in firm"
        )

        access = MatterAccess(
            user_id=body.user_id,
            matter_id=matter_id,
            view_work_product=body.view_work_product,
            assigned_at=datetime.now(UTC),
        )
        db.add(access)

        await commit_or_conflict(db, "Access grant already exists")

        await db.refresh(access)
        matter_access_granted.add(1)
        return _access_to_response(access)


# ---------------------------------------------------------------------------
# DELETE /matters/{matter_id}/access/{user_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{matter_id}/access/{user_id}",
    response_model=MessageResponse,
    responses={404: {}},
)
async def revoke_matter_access(
    matter_id: uuid.UUID,
    user_id: uuid.UUID,
    user: User = Depends(require_role(Role.admin)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    with tracer.start_as_current_span(
        "matter_access.revoke",
        attributes={"user.id": str(user.id), "matter.id": str(matter_id)},
    ):
        await verify_in_firm(matter_id, user.firm_id, db, Matter)

        result = await db.execute(
            select(MatterAccess).where(
                MatterAccess.user_id == user_id,
                MatterAccess.matter_id == matter_id,
            )
        )
        access = result.scalar_one_or_none()

        if access is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        await db.delete(access)
        await db.commit()
        matter_access_revoked.add(1)
        return MessageResponse(detail="Access revoked")
