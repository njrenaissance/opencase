"""Shared helpers for API routers — firm-scoped verification and conflict handling."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.matter import Matter
from app.db.models.user import User


async def verify_in_firm[T: (Matter, User)](
    model_id: uuid.UUID,
    firm_id: uuid.UUID,
    db: AsyncSession,
    model_class: type[T],
    detail: str | None = None,
) -> T:
    """Verify that a model instance belongs to the given firm.

    Raises HTTPException(404) if not found — prevents enumeration.
    """
    result = await db.execute(
        select(model_class).where(
            model_class.id == model_id,  # type: ignore[attr-defined]
            model_class.firm_id == firm_id,  # type: ignore[attr-defined]
        )
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )
    return obj


async def commit_or_conflict(db: AsyncSession, detail: str) -> None:
    """Commit the transaction or raise 409 Conflict on IntegrityError."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from exc
