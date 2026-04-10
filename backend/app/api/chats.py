"""Chats router — stub endpoints for AI chatbot Q&A sessions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from opentelemetry import trace
from shared.models.chat import (
    ChatQueryResponse,
    ChatSessionResponse,
    SubmitQueryRequest,
)

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.metrics import chat_queries_created
from app.db.models.user import User

tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/chats", tags=["chats"])

_STUB_RESPONSE = (
    "This is a stub response. RAG integration is not yet implemented. "
    "In a future release this endpoint will perform a matter-scoped vector search "
    "and return a cited answer from your case documents."
)


# ---------------------------------------------------------------------------
# POST /chats/
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_query(
    body: SubmitQueryRequest,
    user: User = Depends(get_current_user),  # noqa: B008
) -> ChatQueryResponse:
    """Stub — accepts a query and returns a canned response.

    Future: will create or continue a ChatSession, run a matter-scoped RAG
    query against Qdrant, call Ollama for inference, and return a cited answer.
    """
    with tracer.start_as_current_span(
        "chats.submit_query",
        attributes={"user.id": str(user.id), "matter.id": str(body.matter_id)},
    ):
        now = datetime.now(UTC)
        session_id = body.session_id or uuid.uuid4()
        query_id = uuid.uuid4()
        chat_queries_created.add(1)
        return ChatQueryResponse(
            id=query_id,
            session_id=session_id,
            matter_id=body.matter_id,
            query=body.query,
            response=_STUB_RESPONSE,
            model_name=settings.chatbot.model,
            created_at=now,
        )


# ---------------------------------------------------------------------------
# GET /chats/sessions
# ---------------------------------------------------------------------------


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[ChatSessionResponse]:
    """Stub — returns an empty list.

    Future: will query chat_sessions filtered by firm_id and accessible matters.
    """
    with tracer.start_as_current_span(
        "chats.list_sessions",
        attributes={"user.id": str(user.id)},
    ):
        return []
