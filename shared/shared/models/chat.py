"""Pydantic request/response models for chat endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

__all__ = [
    "ChatQueryResponse",
    "ChatSessionResponse",
    "SubmitQueryRequest",
]

# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class SubmitQueryRequest(BaseModel):
    matter_id: UUID
    session_id: UUID | None = None  # None = create a new session
    query: str = Field(min_length=1, max_length=10000)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ChatSessionResponse(BaseModel):
    """A named conversation thread within a matter."""

    id: UUID
    matter_id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ChatQueryResponse(BaseModel):
    """One query/response turn within a chat session."""

    id: UUID
    session_id: UUID
    matter_id: UUID
    query: str
    response: str | None
    model_name: str | None
    created_at: datetime
