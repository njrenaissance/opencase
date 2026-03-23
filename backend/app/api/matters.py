"""Matter router — list, read, create, update matters within the firm."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from opentelemetry import trace
from shared.models.enums import MatterStatus, Role
from shared.models.matter import (
    CreateMatterRequest,
    MatterResponse,
    MatterSummary,
    UpdateMatterRequest,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.metrics import matters_created, matters_updated
from app.core.permissions import require_role
from app.db import get_db
from app.db.models.matter import Matter
from app.db.models.matter_access import MatterAccess
from app.db.models.user import User

tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/matters", tags=["matters"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _matter_to_summary(matter: Matter) -> MatterSummary:
    return MatterSummary(
        id=matter.id,
        name=matter.name,
        client_id=matter.client_id,
        status=matter.status,
        legal_hold=matter.legal_hold,
    )


def _matter_to_response(matter: Matter) -> MatterResponse:
    return MatterResponse(
        id=matter.id,
        name=matter.name,
        client_id=matter.client_id,
        status=matter.status,
        legal_hold=matter.legal_hold,
        firm_id=matter.firm_id,
        created_at=matter.created_at,
        updated_at=matter.updated_at,
    )


# ---------------------------------------------------------------------------
# GET /matters/
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[MatterSummary])
async def list_matters(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[MatterSummary]:
    with tracer.start_as_current_span(
        "matters.list",
        attributes={"user.id": str(user.id)},
    ):
        stmt = select(Matter).where(Matter.firm_id == user.firm_id)

        if user.role != Role.admin:
            stmt = stmt.join(MatterAccess, MatterAccess.matter_id == Matter.id).where(
                MatterAccess.user_id == user.id
            )

        result = await db.execute(stmt)
        return [_matter_to_summary(m) for m in result.scalars().all()]


# ---------------------------------------------------------------------------
# GET /matters/{matter_id}
# ---------------------------------------------------------------------------


@router.get("/{matter_id}", response_model=MatterResponse, responses={404: {}})
async def get_matter(
    matter_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MatterResponse:
    with tracer.start_as_current_span(
        "matters.get",
        attributes={"user.id": str(user.id), "matter.id": str(matter_id)},
    ):
        stmt = select(Matter).where(
            Matter.id == matter_id, Matter.firm_id == user.firm_id
        )

        if user.role != Role.admin:
            stmt = stmt.join(MatterAccess, MatterAccess.matter_id == Matter.id).where(
                MatterAccess.user_id == user.id
            )

        result = await db.execute(stmt)
        matter = result.scalar_one_or_none()

        if matter is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        return _matter_to_response(matter)


# ---------------------------------------------------------------------------
# POST /matters/
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=MatterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_matter(
    body: CreateMatterRequest,
    user: User = Depends(require_role(Role.admin, Role.attorney)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MatterResponse:
    with tracer.start_as_current_span(
        "matters.create",
        attributes={"user.id": str(user.id)},
    ):
        now = datetime.now(UTC)
        matter = Matter(
            id=uuid.uuid4(),
            firm_id=user.firm_id,
            name=body.name,
            client_id=body.client_id,
            status=MatterStatus.open,
            legal_hold=False,
            created_at=now,
            updated_at=now,
        )
        db.add(matter)
        await db.commit()
        await db.refresh(matter)
        matters_created.add(1)
        return _matter_to_response(matter)


# ---------------------------------------------------------------------------
# PATCH /matters/{matter_id}
# ---------------------------------------------------------------------------


@router.patch("/{matter_id}", response_model=MatterResponse, responses={404: {}})
async def update_matter(
    matter_id: uuid.UUID,
    body: UpdateMatterRequest,
    user: User = Depends(require_role(Role.admin, Role.attorney)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MatterResponse:
    with tracer.start_as_current_span(
        "matters.update",
        attributes={"user.id": str(user.id), "matter.id": str(matter_id)},
    ):
        stmt = select(Matter).where(
            Matter.id == matter_id, Matter.firm_id == user.firm_id
        )

        # Non-admin attorneys must be assigned to the matter
        if user.role != Role.admin:
            stmt = stmt.join(MatterAccess, MatterAccess.matter_id == Matter.id).where(
                MatterAccess.user_id == user.id
            )

        result = await db.execute(stmt)
        matter = result.scalar_one_or_none()

        if matter is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        updates = body.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(matter, field, value)

        await db.commit()
        await db.refresh(matter)
        matters_updated.add(1)
        return _matter_to_response(matter)
