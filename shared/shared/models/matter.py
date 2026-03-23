"""Pydantic request/response models for matter endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from shared.models.enums import MatterStatus

# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class MatterSummary(BaseModel):
    """Lightweight matter reference (for lists)."""

    id: UUID
    name: str
    client_id: UUID
    status: MatterStatus
    legal_hold: bool


class MatterResponse(MatterSummary):
    """Full matter detail (single-matter endpoint)."""

    firm_id: UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class CreateMatterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    client_id: UUID


class UpdateMatterRequest(BaseModel):
    """All fields optional — only provided fields are updated."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: MatterStatus | None = None
