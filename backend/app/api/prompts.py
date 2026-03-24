"""Prompt router — stub endpoints for AI chatbot prompts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from opentelemetry import trace
from shared.models.prompt import (
    CreatePromptRequest,
    PromptResponse,
    PromptSummary,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.metrics import prompts_created
from app.db import get_db
from app.db.models.user import User

tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/prompts", tags=["prompts"])

_STUB_RESPONSE = (
    "This is a stub response. RAG integration is not yet implemented. "
    "In the future, this endpoint will perform a matter-scoped vector search "
    "and return a cited answer from your case documents."
)


# ---------------------------------------------------------------------------
# POST /prompts/
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=PromptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_prompt(
    body: CreatePromptRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PromptResponse:
    """Stub — accepts a prompt and returns a canned response.

    Future: will trigger a matter-scoped RAG query against Qdrant and return
    a cited answer.
    """
    with tracer.start_as_current_span(
        "prompts.create",
        attributes={"user.id": str(user.id), "matter.id": str(body.matter_id)},
    ):
        now = datetime.now(UTC)
        prompt_id = uuid.uuid4()
        prompts_created.add(1)
        return PromptResponse(
            id=prompt_id,
            firm_id=user.firm_id,
            matter_id=body.matter_id,
            query=body.query,
            response=_STUB_RESPONSE,
            created_by=user.id,
            created_at=now,
            updated_at=now,
        )


# ---------------------------------------------------------------------------
# GET /prompts/
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[PromptSummary])
async def list_prompts(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[PromptSummary]:
    """Stub — returns an empty list."""
    with tracer.start_as_current_span(
        "prompts.list",
        attributes={"user.id": str(user.id)},
    ):
        return []


# ---------------------------------------------------------------------------
# GET /prompts/{prompt_id}
# ---------------------------------------------------------------------------


@router.get("/{prompt_id}", response_model=PromptResponse, responses={404: {}})
async def get_prompt(
    prompt_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PromptResponse:
    """Stub — always returns 404."""
    with tracer.start_as_current_span(
        "prompts.get",
        attributes={"user.id": str(user.id), "prompt.id": str(prompt_id)},
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
