"""Unit tests for the RAG pipeline (backend/app/rag/pipeline.py).

All external dependencies (httpx, Qdrant, ChatOllama, DB) are mocked.
No running services required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from qdrant_client import models
from shared.models.enums import Role

from app.core.constants import GLOBAL_KNOWLEDGE_MATTER_ID
from app.core.permissions import PermissionFilter
from app.rag.pipeline import (
    _format_context,
    _to_qdrant_filter,
    build_messages,
    embed_query,
    run_query,
    stream_query,
)
from tests.conftest import FakeSession
from tests.factories import make_user

_FIRM_ID = uuid.uuid4()
_MATTER_ID = uuid.uuid4()
_DOC_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scored_point(
    doc_id: str = _DOC_ID,
    chunk_index: int = 0,
    text: str = "Sample chunk text.",
    score: float = 0.87,
    page_number: int | None = 4,
    bates_number: str | None = "DEF-0042",
) -> models.ScoredPoint:
    """Build a minimal ScoredPoint as Qdrant would return from search."""
    return models.ScoredPoint(
        id=str(uuid.uuid4()),
        version=0,
        score=score,
        payload={
            "firm_id": str(_FIRM_ID),
            "matter_id": str(_MATTER_ID),
            "client_id": str(uuid.uuid4()),
            "document_id": doc_id,
            "chunk_index": chunk_index,
            "classification": "unclassified",
            "source": "government_production",
            "bates_number": bates_number,
            "page_number": page_number,
            "text": text,
        },
    )


def _make_perm_filter(
    excluded: frozenset[str] | None = None,
) -> PermissionFilter:
    return PermissionFilter(
        firm_id=_FIRM_ID,
        matter_ids=frozenset({_MATTER_ID, GLOBAL_KNOWLEDGE_MATTER_ID}),
        excluded_classifications=excluded or frozenset(),
    )


# ---------------------------------------------------------------------------
# embed_query
# ---------------------------------------------------------------------------


class TestEmbedQuery:
    @pytest.mark.asyncio
    async def test_calls_ollama_embed_endpoint(self) -> None:
        vector = [0.1] * 768
        mock_response = httpx.Response(
            200,
            json={"embeddings": [vector]},
            request=httpx.Request("POST", "http://ollama:11434/api/embed"),
        )
        with patch("app.rag.pipeline.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = await embed_query("test query")

        assert result == vector
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        body = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
        assert body["input"] == ["test query"]

    @pytest.mark.asyncio
    async def test_http_error_propagates(self) -> None:
        mock_response = httpx.Response(
            500,
            text="Internal Server Error",
            request=httpx.Request("POST", "http://ollama:11434/api/embed"),
        )
        with patch("app.rag.pipeline.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response

            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await embed_query("test query")


# ---------------------------------------------------------------------------
# _to_qdrant_filter
# ---------------------------------------------------------------------------


class TestToQdrantFilter:
    @pytest.mark.parametrize(
        ("excluded", "expect_must_not"),
        [
            (frozenset(), False),  # admin — no exclusions
            (frozenset({"jencks"}), True),  # attorney / paralegal
            (frozenset({"jencks", "work_product"}), True),  # investigator
        ],
    )
    def test_must_not_present_based_on_exclusions(
        self, excluded: frozenset[str], expect_must_not: bool
    ) -> None:
        pf = _make_perm_filter(excluded=excluded)
        f = _to_qdrant_filter(pf)
        has_must_not = bool(f.must_not)
        assert has_must_not == expect_must_not

    def test_both_matter_ids_in_match_any(self) -> None:
        pf = _make_perm_filter()
        f = _to_qdrant_filter(pf)

        matter_condition = next(
            c
            for c in (f.must or [])
            if isinstance(c, models.FieldCondition) and c.key == "matter_id"
        )
        any_values = matter_condition.match.any  # type: ignore[union-attr]
        assert str(_MATTER_ID) in any_values
        assert str(GLOBAL_KNOWLEDGE_MATTER_ID) in any_values

    def test_firm_id_in_must(self) -> None:
        pf = _make_perm_filter()
        f = _to_qdrant_filter(pf)
        firm_condition = next(
            c
            for c in (f.must or [])
            if isinstance(c, models.FieldCondition) and c.key == "firm_id"
        )
        assert firm_condition.match.value == str(_FIRM_ID)  # type: ignore[union-attr]

    def test_excluded_classifications_in_must_not(self) -> None:
        pf = _make_perm_filter(excluded=frozenset({"jencks", "work_product"}))
        f = _to_qdrant_filter(pf)
        class_condition = next(
            c
            for c in (f.must_not or [])
            if isinstance(c, models.FieldCondition) and c.key == "classification"
        )
        any_values = class_condition.match.any  # type: ignore[union-attr]
        assert "jencks" in any_values
        assert "work_product" in any_values


# ---------------------------------------------------------------------------
# _format_context
# ---------------------------------------------------------------------------


class TestFormatContext:
    def test_empty_chunks_returns_no_documents_message(self) -> None:
        result = _format_context([])
        assert "no" in result.lower() or "not found" in result.lower()

    def test_with_bates_and_page(self) -> None:
        point = _make_scored_point(page_number=4, bates_number="DEF-0042")
        result = _format_context([point])
        assert "Page: 4" in result
        assert "Bates: DEF-0042" in result

    def test_without_bates_or_page(self) -> None:
        point = _make_scored_point(page_number=None, bates_number=None)
        result = _format_context([point])
        assert "Page:" not in result
        assert "Bates:" not in result

    def test_chunk_text_appears_in_output(self) -> None:
        point = _make_scored_point(text="Officer observed the defendant at 3rd Ave.")
        result = _format_context([point])
        assert "Officer observed the defendant at 3rd Ave." in result

    def test_multiple_chunks_numbered(self) -> None:
        points = [
            _make_scored_point(text="First chunk."),
            _make_scored_point(text="Second chunk."),
        ]
        result = _format_context(points)
        assert "Source 1" in result
        assert "Source 2" in result


# ---------------------------------------------------------------------------
# build_messages
# ---------------------------------------------------------------------------


class TestBuildMessages:
    def test_returns_two_messages(self) -> None:
        msgs = build_messages("You are Gideon.", "What evidence?", [])
        assert len(msgs) == 2

    def test_roles_are_system_and_user(self) -> None:
        msgs = build_messages("You are Gideon.", "What evidence?", [])
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_system_prompt_in_system_message(self) -> None:
        prompt = "Custom system prompt for testing."
        msgs = build_messages(prompt, "question?", [])
        assert msgs[0]["content"] == prompt

    def test_query_in_user_message(self) -> None:
        msgs = build_messages("sys", "What Brady material exists?", [])
        assert "What Brady material exists?" in msgs[1]["content"]

    def test_chunk_text_in_user_message(self) -> None:
        point = _make_scored_point(text="Highly relevant passage.")
        msgs = build_messages("sys", "query?", [point])
        assert "Highly relevant passage." in msgs[1]["content"]


# ---------------------------------------------------------------------------
# run_query
# ---------------------------------------------------------------------------


def _make_chat_session() -> MagicMock:
    session = MagicMock()
    session.id = uuid.uuid4()
    session.firm_id = _FIRM_ID
    session.matter_id = _MATTER_ID
    return session


def _make_chat_query(session_id: uuid.UUID) -> MagicMock:
    q = MagicMock()
    q.id = uuid.uuid4()
    q.session_id = session_id
    q.query = "test query"
    q.response = "test response"
    q.model_name = "tinyllama"
    q.latency_ms = 1234
    q.created_at = datetime.now(UTC)
    return q


class TestRunQuery:
    @pytest.mark.asyncio
    async def test_build_permission_filter_called_before_search(self) -> None:
        """build_permission_filter must be the first external call."""
        call_order: list[str] = []
        pf = _make_perm_filter()
        fake_session = _make_chat_session()
        fake_query = _make_chat_query(fake_session.id)

        async def _mock_filter(*_: object, **__: object) -> PermissionFilter:
            call_order.append("filter")
            return pf

        async def _mock_embed(*_: object, **__: object) -> list[float]:
            call_order.append("embed")
            return [0.1] * 768

        mock_vectorstore = AsyncMock()
        mock_vectorstore.search.side_effect = lambda *_a, **_kw: (
            call_order.append("search") or []
        )

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="the answer"))

        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        db = FakeSession()

        with (
            patch("app.rag.pipeline.build_permission_filter", _mock_filter),
            patch("app.rag.pipeline.embed_query", _mock_embed),
            patch(
                "app.rag.pipeline.get_vectorstore_service",
                return_value=mock_vectorstore,
            ),
            patch("app.rag.pipeline.ChatOllama", return_value=mock_llm),
            patch(
                "app.rag.pipeline._get_or_create_session",
                AsyncMock(return_value=fake_session),
            ),
            patch("app.rag.pipeline._save_query", AsyncMock(return_value=fake_query)),
        ):
            await run_query("test query", user, _MATTER_ID, None, db)

        assert call_order[0] == "filter"
        assert "embed" in call_order
        assert "search" in call_order

    @pytest.mark.asyncio
    async def test_returns_session_and_query(self) -> None:
        pf = _make_perm_filter()
        fake_session = _make_chat_session()
        fake_query = _make_chat_query(fake_session.id)

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="the answer"))
        mock_vectorstore = AsyncMock()
        mock_vectorstore.search.return_value = []

        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        db = FakeSession()

        with (
            patch(
                "app.rag.pipeline.build_permission_filter",
                AsyncMock(return_value=pf),
            ),
            patch("app.rag.pipeline.embed_query", AsyncMock(return_value=[0.1] * 768)),
            patch(
                "app.rag.pipeline.get_vectorstore_service",
                return_value=mock_vectorstore,
            ),
            patch("app.rag.pipeline.ChatOllama", return_value=mock_llm),
            patch(
                "app.rag.pipeline._get_or_create_session",
                AsyncMock(return_value=fake_session),
            ),
            patch("app.rag.pipeline._save_query", AsyncMock(return_value=fake_query)),
        ):
            session, record = await run_query("test query", user, _MATTER_ID, None, db)

        assert session is fake_session
        assert record is fake_query

    @pytest.mark.asyncio
    async def test_saves_to_db(self) -> None:
        pf = _make_perm_filter()
        fake_session = _make_chat_session()
        fake_query = _make_chat_query(fake_session.id)

        mock_save = AsyncMock(return_value=fake_query)
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="answer"))
        mock_vectorstore = AsyncMock()
        mock_vectorstore.search.return_value = []

        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        db = FakeSession()

        with (
            patch(
                "app.rag.pipeline.build_permission_filter",
                AsyncMock(return_value=pf),
            ),
            patch("app.rag.pipeline.embed_query", AsyncMock(return_value=[0.1] * 768)),
            patch(
                "app.rag.pipeline.get_vectorstore_service",
                return_value=mock_vectorstore,
            ),
            patch("app.rag.pipeline.ChatOllama", return_value=mock_llm),
            patch(
                "app.rag.pipeline._get_or_create_session",
                AsyncMock(return_value=fake_session),
            ),
            patch("app.rag.pipeline._save_query", mock_save),
        ):
            await run_query("my question", user, _MATTER_ID, None, db)

        mock_save.assert_awaited_once()
        # First positional arg after db, session, user is the query text
        assert mock_save.call_args[0][3] == "my question"
        assert mock_save.call_args[0][4] == "answer"


# ---------------------------------------------------------------------------
# stream_query
# ---------------------------------------------------------------------------


class TestStreamQuery:
    @pytest.mark.asyncio
    async def test_yields_tokens_from_llm(self) -> None:
        pf = _make_perm_filter()
        fake_session = _make_chat_session()
        fake_query = _make_chat_query(fake_session.id)

        async def _fake_astream(_messages: object) -> Any:
            for tok in ["Hello", " world", "."]:
                yield MagicMock(content=tok)

        mock_llm = MagicMock()
        mock_llm.astream = _fake_astream
        mock_vectorstore = AsyncMock()
        mock_vectorstore.search.return_value = []

        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        db = FakeSession()

        tokens: list[str] = []
        with (
            patch(
                "app.rag.pipeline.build_permission_filter",
                AsyncMock(return_value=pf),
            ),
            patch("app.rag.pipeline.embed_query", AsyncMock(return_value=[0.1] * 768)),
            patch(
                "app.rag.pipeline.get_vectorstore_service",
                return_value=mock_vectorstore,
            ),
            patch("app.rag.pipeline.ChatOllama", return_value=mock_llm),
            patch(
                "app.rag.pipeline._get_or_create_session",
                AsyncMock(return_value=fake_session),
            ),
            patch("app.rag.pipeline._save_query", AsyncMock(return_value=fake_query)),
        ):
            async for token in stream_query("test query", user, _MATTER_ID, None, db):
                tokens.append(token)

        assert tokens == ["Hello", " world", "."]

    @pytest.mark.asyncio
    async def test_saves_to_db_after_all_tokens_yielded(self) -> None:
        pf = _make_perm_filter()
        fake_session = _make_chat_session()
        fake_query = _make_chat_query(fake_session.id)

        yielded: list[str] = []
        saved_at_token_count: list[int] = []

        async def _fake_astream(_messages: object) -> Any:
            for tok in ["A", "B", "C"]:
                yielded.append(tok)
                yield MagicMock(content=tok)

        mock_save = AsyncMock(
            side_effect=lambda *_a, **_kw: (
                saved_at_token_count.append(len(yielded)) or fake_query
            )
        )

        mock_llm = MagicMock()
        mock_llm.astream = _fake_astream
        mock_vectorstore = AsyncMock()
        mock_vectorstore.search.return_value = []

        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        db = FakeSession()

        with (
            patch(
                "app.rag.pipeline.build_permission_filter",
                AsyncMock(return_value=pf),
            ),
            patch("app.rag.pipeline.embed_query", AsyncMock(return_value=[0.1] * 768)),
            patch(
                "app.rag.pipeline.get_vectorstore_service",
                return_value=mock_vectorstore,
            ),
            patch("app.rag.pipeline.ChatOllama", return_value=mock_llm),
            patch(
                "app.rag.pipeline._get_or_create_session",
                AsyncMock(return_value=fake_session),
            ),
            patch("app.rag.pipeline._save_query", mock_save),
        ):
            async for _ in stream_query("test query", user, _MATTER_ID, None, db):
                pass

        # save must have been called after all 3 tokens were yielded
        mock_save.assert_awaited_once()
        assert saved_at_token_count[0] == 3

    @pytest.mark.asyncio
    async def test_full_response_joined_before_save(self) -> None:
        pf = _make_perm_filter()
        fake_session = _make_chat_session()
        fake_query = _make_chat_query(fake_session.id)

        async def _fake_astream(_messages: object) -> Any:
            for tok in ["Hello", " ", "world"]:
                yield MagicMock(content=tok)

        mock_save = AsyncMock(return_value=fake_query)
        mock_llm = MagicMock()
        mock_llm.astream = _fake_astream
        mock_vectorstore = AsyncMock()
        mock_vectorstore.search.return_value = []

        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        db = FakeSession()

        with (
            patch(
                "app.rag.pipeline.build_permission_filter",
                AsyncMock(return_value=pf),
            ),
            patch("app.rag.pipeline.embed_query", AsyncMock(return_value=[0.1] * 768)),
            patch(
                "app.rag.pipeline.get_vectorstore_service",
                return_value=mock_vectorstore,
            ),
            patch("app.rag.pipeline.ChatOllama", return_value=mock_llm),
            patch(
                "app.rag.pipeline._get_or_create_session",
                AsyncMock(return_value=fake_session),
            ),
            patch("app.rag.pipeline._save_query", mock_save),
        ):
            async for _ in stream_query("q", user, _MATTER_ID, None, db):
                pass

        # response argument (positional index 4) should be joined tokens
        saved_response = mock_save.call_args[0][4]
        assert saved_response == "Hello world"
