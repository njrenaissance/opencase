"""Firm router — read-only access to the authenticated user's firm."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from opentelemetry import trace
from shared.models.firm import FirmResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db import get_db
from app.db.models.firm import Firm
from app.db.models.user import User

tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/firms", tags=["firms"])


@router.get("/me", response_model=FirmResponse)
async def get_current_firm(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> FirmResponse:
    with tracer.start_as_current_span(
        "firms.get_current",
        attributes={"user.id": str(user.id)},
    ):
        result = await db.execute(select(Firm).where(Firm.id == user.firm_id))
        firm = result.scalar_one_or_none()

        if firm is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        return FirmResponse(
            id=firm.id,
            name=firm.name,
            created_at=firm.created_at,
        )
