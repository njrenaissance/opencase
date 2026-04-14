"""RAG pipeline — embed query, retrieve chunks, assemble prompt, run inference.

This module is the core of Feature 7.3. It wires together:
  - Qdrant similarity search (always gated by build_qdrant_filter)
  - Ollama embedding for query vectorisation
  - Prompt assembly (SYSTEM_PROMPT + retrieved context + user query)
  - Ollama inference via LangChain ChatOllama (non-streaming and streaming)
  - ChatSession / ChatQuery persistence

build_qdrant_filter() is called first in every entrypoint and is never
bypassed. The PermissionFilter it returns is converted to a
qdrant_client.models.Filter before any search is issued.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import httpx
from fastapi import HTTPException, status
from langchain_ollama import ChatOllama
from opentelemetry import trace
from opentelemetry.trace import StatusCode
from qdrant_client import models
from qdrant_client.models import FieldCondition, MatchAny, MatchValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.permissions import PermissionFilter, build_qdrant_filter
from app.db.models.chat_query import ChatQuery
from app.db.models.chat_session import ChatSession
from app.db.models.user import User
from app.vectorstore import get_vectorstore_service

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


# ---------------------------------------------------------------------------
# Query embedding
# ---------------------------------------------------------------------------


async def embed_query(text: str) -> list[float]:
    """Embed a single query string via Ollama /api/embed.

    Uses the same model and base_url as ``EmbeddingService`` (both read from
    ``settings.embedding``) but operates on a single string without the
    chunk-dict overhead of the ingestion path.

    Args:
        text: The user's natural-language query.

    Returns:
        768-dimensional embedding vector.

    Raises:
        httpx.HTTPStatusError: If Ollama returns a non-2xx response.
        httpx.ConnectError: If Ollama is unreachable.
    """
    async with httpx.AsyncClient(
        base_url=settings.embedding.base_url,
        timeout=settings.embedding.request_timeout,
    ) as client:
        response = await client.post(
            "/api/embed",
            json={"model": settings.embedding.model, "input": [text]},
        )
        response.raise_for_status()
        embeddings: list[list[float]] = response.json()["embeddings"]
        return embeddings[0]


# ---------------------------------------------------------------------------
# PermissionFilter → qdrant_client.models.Filter
# ---------------------------------------------------------------------------


def _to_qdrant_filter(pf: PermissionFilter) -> models.Filter:
    """Convert a PermissionFilter to a qdrant_client Filter.

    ``matter_ids`` always includes the requested matter plus
    ``GLOBAL_KNOWLEDGE_MATTER_ID`` (set by ``build_qdrant_filter``).
    ``excluded_classifications`` is empty for admin, contains ``jencks``
    for attorney/paralegal, and ``jencks`` + ``work_product`` for investigator.

    Args:
        pf: Qdrant-agnostic permission filter from ``build_qdrant_filter()``.

    Returns:
        A ``qdrant_client.models.Filter`` ready to pass to ``client.search()``.
    """
    must = [
        FieldCondition(key="firm_id", match=MatchValue(value=str(pf.firm_id))),
        FieldCondition(
            key="matter_id",
            match=MatchAny(any=[str(m) for m in pf.matter_ids]),
        ),
    ]
    must_not: list[FieldCondition] = []
    if pf.excluded_classifications:
        must_not = [
            FieldCondition(
                key="classification",
                match=MatchAny(any=list(pf.excluded_classifications)),
            )
        ]
    return models.Filter(must=must, must_not=must_not)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Context block formatting
# ---------------------------------------------------------------------------


def _format_context(chunks: list[models.ScoredPoint]) -> str:
    """Format retrieved chunks into a numbered context block for the prompt.

    Each chunk is rendered as a citation header followed by its text.
    Page number and Bates number are omitted when not present.

    Args:
        chunks: Scored points returned by Qdrant search, with payload.

    Returns:
        Multi-line string ready to embed in the user message.
    """
    if not chunks:
        return "No relevant documents were found for this query."

    parts: list[str] = []
    for i, point in enumerate(chunks, 1):
        p = point.payload or {}
        doc_id = str(p.get("document_id", ""))[:8]
        page = p.get("page_number")
        bates = p.get("bates_number")
        text = str(p.get("text", ""))

        header_parts = [f"Source {i}", f"Doc: {doc_id}"]
        if page is not None:
            header_parts.append(f"Page: {page}")
        if bates:
            header_parts.append(f"Bates: {bates}")

        parts.append(f"[{' | '.join(header_parts)}]\n{text}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def build_messages(
    system_prompt: str,
    query: str,
    chunks: list[models.ScoredPoint],
) -> list[dict[str, str]]:
    """Assemble the system + user messages for Ollama chat inference.

    The user message embeds the retrieved context block above the question
    so the model can ground its answer in the retrieved documents.

    Args:
        system_prompt: Loaded from ``settings.chatbot.system_prompt``
            (sourced from SYSTEM_PROMPT.md or the built-in default).
        query: The user's natural-language question.
        chunks: Retrieved Qdrant points with text payload.

    Returns:
        Two-element list: [{role: system, ...}, {role: user, ...}].
    """
    context = _format_context(chunks)
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Context from case documents:\n\n{context}\n\nQuestion: {query}"
            ),
        },
    ]


# ---------------------------------------------------------------------------
# Session + query persistence
# ---------------------------------------------------------------------------


async def _get_or_create_session(
    db: AsyncSession,
    user: User,
    matter_id: uuid.UUID,
    session_id: uuid.UUID | None,
) -> ChatSession:
    """Return an existing ChatSession or create a new one.

    Args:
        db: Async database session.
        user: Authenticated user (provides firm_id, id).
        matter_id: Matter being queried.
        session_id: Client-supplied session UUID, or None to create.

    Returns:
        The ChatSession ORM object.

    Raises:
        HTTPException(404): If a supplied session_id doesn't belong to
            this user's firm + matter.
    """
    if session_id is not None:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.firm_id == user.firm_id,
                ChatSession.matter_id == matter_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return session

    session = ChatSession(
        firm_id=user.firm_id,
        matter_id=matter_id,
        created_by=user.id,
        title=None,
    )
    db.add(session)
    await db.flush()  # assign id without committing
    return session


async def _save_query(
    db: AsyncSession,
    session: ChatSession,
    user: User,
    query: str,
    response: str,
    chunks: list[models.ScoredPoint],
    latency_ms: int,
) -> ChatQuery:
    """Persist a ChatQuery row with retrieval context.

    ``retrieval_context`` stores the document_id, chunk_index, and
    similarity score for each retrieved chunk. The text itself lives in
    Qdrant and is not duplicated here. Bates/page citation assembly is
    deferred to Feature 7.5.

    Args:
        db: Async database session.
        session: Parent ChatSession (must already have an id).
        user: Authenticated user.
        query: The user's question text.
        response: The full LLM response text.
        chunks: Retrieved Qdrant points (for retrieval_context logging).
        latency_ms: Wall-clock ms from pipeline start to LLM response.

    Returns:
        The persisted ChatQuery ORM object.
    """
    retrieval_context = {
        "chunks": [
            {
                "document_id": str((point.payload or {}).get("document_id", "")),
                "chunk_index": int((point.payload or {}).get("chunk_index", 0)),
                "score": round(float(point.score), 4),
            }
            for point in chunks
        ]
    }

    chat_query = ChatQuery(
        session_id=session.id,
        user_id=user.id,
        query=query,
        response=response,
        model_name=settings.chatbot.model,
        retrieval_context=retrieval_context,
        latency_ms=latency_ms,
    )
    db.add(chat_query)
    await db.commit()
    await db.refresh(chat_query)
    return chat_query


# ---------------------------------------------------------------------------
# Non-streaming entrypoint
# ---------------------------------------------------------------------------


async def run_query(
    query: str,
    user: User,
    matter_id: uuid.UUID,
    session_id: uuid.UUID | None,
    db: AsyncSession,
) -> tuple[ChatSession, ChatQuery]:
    """Full non-streaming RAG pipeline: retrieve → prompt → infer → persist.

    Steps (order is security-critical):
      1. build_qdrant_filter — permission gate, always first
      2. embed_query — vectorise the user's question
      3. _to_qdrant_filter — convert abstract filter to Qdrant model
      4. vectorstore.search — retrieve top-K permission-filtered chunks
      5. build_messages — assemble SYSTEM_PROMPT + context + question
      6. ChatOllama.ainvoke — run inference
      7. _get_or_create_session + _save_query — persist to DB

    Args:
        query: The user's natural-language question.
        user: Authenticated user from JWT.
        matter_id: Matter to query (validated by build_qdrant_filter).
        session_id: Existing session UUID, or None to create.
        db: Async database session.

    Returns:
        Tuple of (ChatSession, ChatQuery) after DB commit.

    Raises:
        HTTPException(404): If the user has no access to the matter.
        HTTPException(400): If matter_id is a system matter.
        httpx.ConnectError: If Ollama is unreachable.
    """
    start = time.monotonic()

    with tracer.start_as_current_span(
        "rag.run_query",
        attributes={"user.id": str(user.id), "matter.id": str(matter_id)},
    ) as span:
        try:
            # 1. Permission gate — must be first
            perm_filter = await build_qdrant_filter(user, matter_id, db)

            # 2. Embed the query
            query_vector = await embed_query(query)

            # 3. Convert to Qdrant filter
            qdrant_filter = _to_qdrant_filter(perm_filter)

            # 4. Retrieve top-K permission-filtered chunks
            vectorstore = get_vectorstore_service()
            chunks = await vectorstore.search(
                query_vector,
                qdrant_filter,
                settings.chatbot.retrieval_chunk_count,
            )

            # 5. Assemble prompt
            messages = build_messages(settings.chatbot.system_prompt, query, chunks)

            # 6. Run inference
            llm = ChatOllama(
                model=settings.chatbot.model,
                temperature=settings.chatbot.temperature,
                base_url=settings.chatbot.base_url,
                num_predict=settings.chatbot.max_tokens,
            )
            ai_msg = await llm.ainvoke(messages)
            response_text = str(ai_msg.content)

            latency_ms = int((time.monotonic() - start) * 1000)
            span.set_attribute("rag.latency_ms", latency_ms)
            span.set_attribute("rag.chunk_count", len(chunks))

            # 7. Persist
            session = await _get_or_create_session(db, user, matter_id, session_id)
            record = await _save_query(
                db, session, user, query, response_text, chunks, latency_ms
            )

            return session, record

        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise


# ---------------------------------------------------------------------------
# Streaming entrypoint
# ---------------------------------------------------------------------------


async def stream_query(
    query: str,
    user: User,
    matter_id: uuid.UUID,
    session_id: uuid.UUID | None,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Streaming RAG pipeline: retrieve → prompt → stream infer → persist.

    Yields individual text tokens as they arrive from Ollama. After the
    generator is exhausted, persists the full response to the database.
    The db session (from FastAPI's Depends(get_db)) remains open until
    the StreamingResponse generator is fully consumed, so the final
    await is safe.

    Steps 1–5 are identical to run_query. Step 6 uses ChatOllama.astream.

    Args:
        query: The user's natural-language question.
        user: Authenticated user from JWT.
        matter_id: Matter to query (validated by build_qdrant_filter).
        session_id: Existing session UUID, or None to create.
        db: Async database session.

    Yields:
        Individual response text tokens (strings).

    Raises:
        HTTPException(404): If the user has no access to the matter.
        HTTPException(400): If matter_id is a system matter.
        httpx.ConnectError: If Ollama is unreachable.
    """
    start = time.monotonic()

    with tracer.start_as_current_span(
        "rag.stream_query",
        attributes={"user.id": str(user.id), "matter.id": str(matter_id)},
    ) as span:
        try:
            # 1. Permission gate — must be first
            perm_filter = await build_qdrant_filter(user, matter_id, db)

            # 2. Embed the query
            query_vector = await embed_query(query)

            # 3. Convert to Qdrant filter
            qdrant_filter = _to_qdrant_filter(perm_filter)

            # 4. Retrieve top-K permission-filtered chunks
            vectorstore = get_vectorstore_service()
            chunks = await vectorstore.search(
                query_vector,
                qdrant_filter,
                settings.chatbot.retrieval_chunk_count,
            )

            # 5. Assemble prompt
            messages = build_messages(settings.chatbot.system_prompt, query, chunks)

            # 6. Stream inference
            llm = ChatOllama(
                model=settings.chatbot.model,
                temperature=settings.chatbot.temperature,
                base_url=settings.chatbot.base_url,
                num_predict=settings.chatbot.max_tokens,
            )

            full_response: list[str] = []
            async for chunk in llm.astream(messages):
                token = str(chunk.content)
                full_response.append(token)
                yield token

            latency_ms = int((time.monotonic() - start) * 1000)
            span.set_attribute("rag.latency_ms", latency_ms)
            span.set_attribute("rag.chunk_count", len(chunks))

            # 7. Persist — db session is still alive at this point
            session = await _get_or_create_session(db, user, matter_id, session_id)
            await _save_query(
                db, session, user, query, "".join(full_response), chunks, latency_ms
            )

        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise


# ---------------------------------------------------------------------------
# Public re-exports (for import convenience in chats.py)
# ---------------------------------------------------------------------------

__all__ = [
    "build_messages",
    "embed_query",
    "run_query",
    "stream_query",
]
