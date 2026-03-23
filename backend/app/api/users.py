"""User router — list, read, create, update users within the firm."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from opentelemetry import trace
from shared.models.enums import Role
from shared.models.user import (
    CreateUserRequest,
    UpdateUserRequest,
    UserResponse,
    UserSummary,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.helpers import commit_or_conflict
from app.core.auth import get_current_user, hash_password
from app.core.metrics import users_created, users_updated
from app.core.permissions import require_role
from app.db import get_db
from app.db.models.user import User

tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user_to_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        is_active=user.is_active,
    )


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        is_active=user.is_active,
        title=user.title,
        middle_initial=user.middle_initial,
        totp_enabled=user.totp_enabled,
        firm_id=user.firm_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    user: User = Depends(get_current_user),  # noqa: B008
) -> UserResponse:
    with tracer.start_as_current_span(
        "users.get_current",
        attributes={"user.id": str(user.id)},
    ):
        return _user_to_response(user)


# ---------------------------------------------------------------------------
# GET /users/
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[UserSummary])
async def list_users(
    user: User = Depends(require_role(Role.admin, Role.attorney, Role.paralegal)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[UserSummary]:
    with tracer.start_as_current_span(
        "users.list",
        attributes={"user.id": str(user.id)},
    ):
        result = await db.execute(select(User).where(User.firm_id == user.firm_id))
        return [_user_to_summary(u) for u in result.scalars().all()]


# ---------------------------------------------------------------------------
# GET /users/{user_id}
# ---------------------------------------------------------------------------


@router.get("/{user_id}", response_model=UserResponse, responses={404: {}})
async def get_user(
    user_id: uuid.UUID,
    user: User = Depends(require_role(Role.admin, Role.attorney, Role.paralegal)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserResponse:
    with tracer.start_as_current_span(
        "users.get",
        attributes={"user.id": str(user.id), "target.user_id": str(user_id)},
    ):
        result = await db.execute(
            select(User).where(User.id == user_id, User.firm_id == user.firm_id)
        )
        target = result.scalar_one_or_none()

        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        return _user_to_response(target)


# ---------------------------------------------------------------------------
# POST /users/
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {}},
)
async def create_user(
    body: CreateUserRequest,
    user: User = Depends(require_role(Role.admin)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserResponse:
    with tracer.start_as_current_span(
        "users.create",
        attributes={"user.id": str(user.id)},
    ):
        now = datetime.now(UTC)
        new_user = User(
            id=uuid.uuid4(),
            firm_id=user.firm_id,
            email=body.email,
            hashed_password=hash_password(body.password),
            first_name=body.first_name,
            last_name=body.last_name,
            role=body.role,
            title=body.title,
            middle_initial=body.middle_initial,
            is_active=True,
            totp_enabled=False,
            created_at=now,
            updated_at=now,
        )
        db.add(new_user)

        await commit_or_conflict(
            db, "A user with this email already exists in the firm"
        )

        await db.refresh(new_user)
        users_created.add(1)
        return _user_to_response(new_user)


# ---------------------------------------------------------------------------
# PATCH /users/{user_id}
# ---------------------------------------------------------------------------


@router.patch("/{user_id}", response_model=UserResponse, responses={404: {}, 409: {}})
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    user: User = Depends(require_role(Role.admin)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserResponse:
    with tracer.start_as_current_span(
        "users.update",
        attributes={"user.id": str(user.id), "target.user_id": str(user_id)},
    ):
        result = await db.execute(
            select(User).where(User.id == user_id, User.firm_id == user.firm_id)
        )
        target = result.scalar_one_or_none()

        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        updates = body.model_dump(exclude_unset=True)

        if updates.get("is_active") is False and user_id == user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account",
            )

        for field, value in updates.items():
            setattr(target, field, value)

        await commit_or_conflict(
            db, "A user with this email already exists in the firm"
        )

        await db.refresh(target)
        users_updated.add(1)
        return _user_to_response(target)
