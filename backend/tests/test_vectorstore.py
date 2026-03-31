"""Unit tests for the vectorstore module."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import EmbeddingSettings, QdrantSettings
from app.embedding.models import EmbeddingResult
from app.vectorstore.models import (
    POINT_ID_NAMESPACE,
    REQUIRED_METADATA_KEYS,
    VectorPayload,
    make_point_id,
)
from app.vectorstore.service import QdrantVectorStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_qdrant_settings(**overrides: Any) -> QdrantSettings:
    defaults: dict[str, Any] = {
        "host": "localhost",
        "port": 6333,
        "grpc_port": 6334,
        "collection": "opencase_test",
        "prefer_grpc": False,
        "use_ssl": False,
        "api_key": None,
    }
    defaults.update(overrides)
    return QdrantSettings(**defaults)


def _make_embedding_settings(**overrides: Any) -> EmbeddingSettings:
    defaults: dict[str, Any] = {
        "provider": "ollama",
        "model": "nomic-embed-text",
        "base_url": "http://ollama:11434",
        "dimensions": 768,
        "batch_size": 100,
        "request_timeout": 120,
    }
    defaults.update(overrides)
    return EmbeddingSettings(**defaults)


def _fake_vector(dimensions: int = 768) -> list[float]:
    return [0.1] * dimensions


def _make_embedding(
    document_id: str = "doc-1",
    chunk_index: int = 0,
    text: str = "hello world",
    dimensions: int = 768,
    metadata: dict[str, object] | None = None,
) -> EmbeddingResult:
    return EmbeddingResult(
        document_id=document_id,
        chunk_index=chunk_index,
        vector=_fake_vector(dimensions),
        text=text,
        metadata=metadata or {},
    )


def _make_payload_metadata(**overrides: Any) -> dict[str, object]:
    defaults: dict[str, object] = {
        "firm_id": "firm-aaa",
        "matter_id": "matter-bbb",
        "client_id": "client-ccc",
        "classification": "unclassified",
        "source": "government_production",
        "bates_number": None,
        "page_number": None,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# TestVectorPayload
# ---------------------------------------------------------------------------


class TestVectorPayload:
    def test_required_metadata_keys_are_subset_of_payload(self) -> None:
        payload_keys = set(VectorPayload.__annotations__)
        # Required metadata keys + per-chunk keys = full payload
        per_chunk_keys = {"document_id", "chunk_index"}
        optional_keys = {"bates_number", "page_number"}
        assert REQUIRED_METADATA_KEYS | per_chunk_keys | optional_keys == payload_keys

    def test_required_metadata_keys_frozen(self) -> None:
        assert isinstance(REQUIRED_METADATA_KEYS, frozenset)


# ---------------------------------------------------------------------------
# TestPointId
# ---------------------------------------------------------------------------


class TestPointId:
    def test_deterministic(self) -> None:
        id1 = make_point_id("doc-1", 0)
        id2 = make_point_id("doc-1", 0)
        assert id1 == id2

    def test_different_document_ids(self) -> None:
        id1 = make_point_id("doc-1", 0)
        id2 = make_point_id("doc-2", 0)
        assert id1 != id2

    def test_different_chunk_indices(self) -> None:
        id1 = make_point_id("doc-1", 0)
        id2 = make_point_id("doc-1", 1)
        assert id1 != id2

    def test_returns_valid_uuid_string(self) -> None:
        point_id = make_point_id("doc-1", 0)
        parsed = uuid.UUID(point_id)
        assert parsed.version == 5

    def test_uses_fixed_namespace(self) -> None:
        expected = str(uuid.uuid5(POINT_ID_NAMESPACE, "doc-1:0"))
        assert make_point_id("doc-1", 0) == expected


# ---------------------------------------------------------------------------
# TestQdrantVectorStoreUpsert
# ---------------------------------------------------------------------------


class TestQdrantVectorStoreUpsert:
    @pytest.fixture()
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.upsert = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture()
    def store(self, mock_client: AsyncMock) -> QdrantVectorStore:
        qs = _make_qdrant_settings()
        es = _make_embedding_settings()
        svc = QdrantVectorStore(qs, es)
        svc._client = mock_client
        return svc

    @pytest.mark.asyncio()
    async def test_upsert_single_embedding(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        emb = _make_embedding()
        meta = _make_payload_metadata()

        count = await store.upsert_vectors([emb], meta)

        assert count == 1
        mock_client.upsert.assert_called_once()
        call_kwargs = mock_client.upsert.call_args
        assert call_kwargs.kwargs["collection_name"] == "opencase_test"
        points = call_kwargs.kwargs["points"]
        assert len(points) == 1

    @pytest.mark.asyncio()
    async def test_upsert_point_has_correct_id(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        emb = _make_embedding(document_id="doc-42", chunk_index=7)
        meta = _make_payload_metadata()

        await store.upsert_vectors([emb], meta)

        point = mock_client.upsert.call_args.kwargs["points"][0]
        expected_id = make_point_id("doc-42", 7)
        assert point.id == expected_id

    @pytest.mark.asyncio()
    async def test_upsert_point_has_correct_payload(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        emb = _make_embedding(document_id="doc-1", chunk_index=3)
        meta = _make_payload_metadata(
            firm_id="firm-x",
            matter_id="matter-y",
            client_id="client-z",
            classification="brady",
            source="defense",
            bates_number="GOV-001",
            page_number=5,
        )

        await store.upsert_vectors([emb], meta)

        payload = mock_client.upsert.call_args.kwargs["points"][0].payload
        assert payload["firm_id"] == "firm-x"
        assert payload["matter_id"] == "matter-y"
        assert payload["client_id"] == "client-z"
        assert payload["document_id"] == "doc-1"
        assert payload["chunk_index"] == 3
        assert payload["classification"] == "brady"
        assert payload["source"] == "defense"
        assert payload["bates_number"] == "GOV-001"
        assert payload["page_number"] == 5

    @pytest.mark.asyncio()
    async def test_upsert_point_has_vector(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        emb = _make_embedding()
        meta = _make_payload_metadata()

        await store.upsert_vectors([emb], meta)

        point = mock_client.upsert.call_args.kwargs["points"][0]
        assert point.vector == emb.vector

    @pytest.mark.asyncio()
    async def test_upsert_empty_list(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        count = await store.upsert_vectors([], _make_payload_metadata())
        assert count == 0
        mock_client.upsert.assert_not_called()

    @pytest.mark.asyncio()
    async def test_upsert_bates_number_null(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        emb = _make_embedding()
        meta = _make_payload_metadata(bates_number=None)

        await store.upsert_vectors([emb], meta)

        payload = mock_client.upsert.call_args.kwargs["points"][0].payload
        assert payload["bates_number"] is None

    @pytest.mark.asyncio()
    async def test_upsert_batches_large_sets(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        embeddings = [_make_embedding(chunk_index=i) for i in range(250)]
        meta = _make_payload_metadata()

        count = await store.upsert_vectors(embeddings, meta)

        assert count == 250
        # 250 / 100 = 3 batches
        assert mock_client.upsert.call_count == 3

    @pytest.mark.asyncio()
    @pytest.mark.parametrize("missing_key", sorted(REQUIRED_METADATA_KEYS))
    async def test_upsert_missing_required_key_raises(
        self, store: QdrantVectorStore, missing_key: str
    ) -> None:
        meta = _make_payload_metadata()
        del meta[missing_key]
        emb = _make_embedding()

        with pytest.raises(ValueError, match="missing required keys"):
            await store.upsert_vectors([emb], meta)


# ---------------------------------------------------------------------------
# TestQdrantVectorStoreDelete
# ---------------------------------------------------------------------------


class TestQdrantVectorStoreDelete:
    @pytest.fixture()
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.scroll = AsyncMock(return_value=([], None))
        client.delete = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture()
    def store(self, mock_client: AsyncMock) -> QdrantVectorStore:
        qs = _make_qdrant_settings()
        es = _make_embedding_settings()
        svc = QdrantVectorStore(qs, es)
        svc._client = mock_client
        return svc

    @pytest.mark.asyncio()
    async def test_delete_calls_client(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        # Simulate 3 existing points
        fake_points = [MagicMock() for _ in range(3)]
        mock_client.scroll.return_value = (fake_points, None)

        count = await store.delete_by_document("doc-1")

        assert count == 3
        mock_client.delete.assert_called_once()

    @pytest.mark.asyncio()
    async def test_delete_no_matching_points(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        mock_client.scroll.return_value = ([], None)

        count = await store.delete_by_document("doc-nonexistent")

        assert count == 0
        mock_client.delete.assert_called_once()


# ---------------------------------------------------------------------------
# TestFactory
# ---------------------------------------------------------------------------


class TestFactory:
    def test_singleton_returns_same_instance(self) -> None:
        import app.vectorstore as mod

        mod._service = None  # reset

        mock_settings = MagicMock()
        mock_settings.qdrant = _make_qdrant_settings()
        mock_settings.embedding = _make_embedding_settings()

        with patch("app.core.config.settings", mock_settings):
            from app.vectorstore import get_vectorstore_service

            svc1 = get_vectorstore_service()
            svc2 = get_vectorstore_service()
            assert svc1 is svc2

        mod._service = None  # cleanup
