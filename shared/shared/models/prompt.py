"""Pydantic request/response models for prompt endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class PromptSummary(BaseModel):
    """Lightweight prompt reference (for lists)."""

    id: UUID
    matter_id: UUID
    query: str
    created_at: datetime


class PromptResponse(PromptSummary):
    """Full prompt detail (single-prompt endpoint)."""

    firm_id: UUID
    response: str | None
    created_by: UUID
    updated_at: datetime


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class CreatePromptRequest(BaseModel):
    matter_id: UUID
    query: str = Field(min_length=1, max_length=10000)
