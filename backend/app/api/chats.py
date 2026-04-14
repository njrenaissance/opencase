"""Chats router — matter-scoped RAG chatbot Q&A sessions."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from shared.models.chat import (
    ChatQueryResponse,
    ChatSessionResponse,
    SubmitQueryRequest,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.metrics import chat_queries_created
from app.db import get_db
from app.db.models.user import User
from app.rag.pipeline import run_query, stream_query

tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/chats", tags=["chats"])


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
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ChatQueryResponse:
    """Run a matter-scoped RAG query and return the full response.

    Retrieves the top-K most semantically relevant chunks from Qdrant
    (permission-filtered via ``build_qdrant_filter``), assembles a prompt
    with the SYSTEM_PROMPT and retrieved context, calls Ollama for inference,
    and persists the query + response to the database.
    """
    with tracer.start_as_current_span(
        "chats.submit_query",
        attributes={"user.id": str(user.id), "matter.id": str(body.matter_id)},
    ):
        session, record = await run_query(
            body.query, user, body.matter_id, body.session_id, db
        )
        chat_queries_created.add(1)
        return ChatQueryResponse(
            id=record.id,
            session_id=session.id,
            matter_id=session.matter_id,
            query=record.query,
            response=record.response,
            model_name=record.model_name,
            created_at=record.created_at,
        )


# ---------------------------------------------------------------------------
# POST /chats/stream
# ---------------------------------------------------------------------------


@router.post("/stream")
async def submit_query_stream(
    body: SubmitQueryRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> StreamingResponse:
    """Stream a matter-scoped RAG response as Server-Sent Events.

    Performs the same retrieval + prompt assembly as ``submit_query``,
    but yields individual tokens as ``data: {"token": "..."}`` SSE lines.
    Terminates with ``data: [DONE]``, or ``data: {"error": "..."}``
    followed by ``data: [DONE]`` if inference fails mid-stream.

    The database record is saved after the stream is fully consumed
    (the db session remains open until the generator is exhausted).
    The OpenTelemetry span covers the full stream lifetime, not just
    the setup, so latency and errors are correctly attributed.
    """
    span = tracer.start_span(
        "chats.submit_query_stream",
        attributes={"user.id": str(user.id), "matter.id": str(body.matter_id)},
    )
    gen = stream_query(body.query, user, body.matter_id, body.session_id, db)

    async def _sse() -> AsyncGenerator[bytes, None]:
        try:
            async for token in gen:
                yield f"data: {json.dumps({'token': token})}\n\n".encode()
            yield b"data: [DONE]\n\n"
        except Exception as exc:
            span.record_exception(exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n".encode()
            yield b"data: [DONE]\n\n"
        finally:
            span.end()

    return StreamingResponse(_sse(), media_type="text/event-stream")


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
