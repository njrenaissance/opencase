"""Unit tests for the vectorstore module."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.vectorstore.models import (
    POINT_ID_NAMESPACE,
    REQUIRED_METADATA_KEYS,
    VectorPayload,
    make_point_id,
)
from app.vectorstore.service import QdrantVectorStore
from tests.factories import (
    make_embedding_result,
    make_embedding_settings,
    make_payload_metadata,
    make_qdrant_settings,
)

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
        qs = make_qdrant_settings()
        es = make_embedding_settings()
        svc = QdrantVectorStore(qs, es)
        svc._client = mock_client
        return svc

    @pytest.mark.asyncio()
    async def test_upsert_single_embedding(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        emb = make_embedding_result()
        meta = make_payload_metadata()

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
        emb = make_embedding_result(document_id="doc-42", chunk_index=7)
        meta = make_payload_metadata()

        await store.upsert_vectors([emb], meta)

        point = mock_client.upsert.call_args.kwargs["points"][0]
        expected_id = make_point_id("doc-42", 7)
        assert point.id == expected_id

    @pytest.mark.asyncio()
    async def test_upsert_point_has_correct_payload(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        emb = make_embedding_result(document_id="doc-1", chunk_index=3)
        meta = make_payload_metadata(
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
        emb = make_embedding_result()
        meta = make_payload_metadata()

        await store.upsert_vectors([emb], meta)

        point = mock_client.upsert.call_args.kwargs["points"][0]
        assert point.vector == emb.vector

    @pytest.mark.asyncio()
    async def test_upsert_empty_list(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        count = await store.upsert_vectors([], make_payload_metadata())
        assert count == 0
        mock_client.upsert.assert_not_called()

    @pytest.mark.asyncio()
    async def test_upsert_bates_number_null(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        emb = make_embedding_result()
        meta = make_payload_metadata(bates_number=None)

        await store.upsert_vectors([emb], meta)

        payload = mock_client.upsert.call_args.kwargs["points"][0].payload
        assert payload["bates_number"] is None

    @pytest.mark.asyncio()
    async def test_upsert_batches_large_sets(
        self, store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        embeddings = [make_embedding_result(chunk_index=i) for i in range(250)]
        meta = make_payload_metadata()

        count = await store.upsert_vectors(embeddings, meta)

        assert count == 250
        # 250 / 100 = 3 batches
        assert mock_client.upsert.call_count == 3

    @pytest.mark.asyncio()
    @pytest.mark.parametrize("missing_key", sorted(REQUIRED_METADATA_KEYS))
    async def test_upsert_missing_required_key_raises(
        self, store: QdrantVectorStore, missing_key: str
    ) -> None:
        meta = make_payload_metadata()
        del meta[missing_key]
        emb = make_embedding_result()

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
        qs = make_qdrant_settings()
        es = make_embedding_settings()
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
        mock_settings.qdrant = make_qdrant_settings()
        mock_settings.embedding = make_embedding_settings()

        with patch("app.core.config.settings", mock_settings):
            from app.vectorstore import get_vectorstore_service

            svc1 = get_vectorstore_service()
            svc2 = get_vectorstore_service()
            assert svc1 is svc2

        mod._service = None  # cleanup
