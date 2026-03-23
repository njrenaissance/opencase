"""Pydantic request/response models for user endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from shared.models.enums import Role

# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class UserSummary(BaseModel):
    """Lightweight user reference (for lists, nested responses)."""

    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    role: Role
    is_active: bool


class UserResponse(UserSummary):
    """Full user detail (single-user endpoint)."""

    title: str | None
    middle_initial: str | None
    totp_enabled: bool
    firm_id: UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: Role
    title: str | None = Field(default=None, max_length=50)
    middle_initial: str | None = Field(default=None, max_length=5)


class UpdateUserRequest(BaseModel):
    """All fields optional — only provided fields are updated."""

    email: EmailStr | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Role | None = None
    title: str | None = Field(default=None, max_length=50)
    middle_initial: str | None = Field(default=None, max_length=5)
    is_active: bool | None = None
