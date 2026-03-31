"""Integration tests for QdrantVectorStore against a live Qdrant instance.

Requires ``docker compose up qdrant`` (or the full stack).
Run with: ``pytest -m integration tests/test_vectorstore_integration.py``
"""

from __future__ import annotations

import contextlib
import uuid
from typing import Any

import pytest
from qdrant_client import AsyncQdrantClient, models

from app.core.config import EmbeddingSettings, QdrantSettings
from app.embedding.models import EmbeddingResult
from app.vectorstore.models import VectorPayload
from app.vectorstore.service import QdrantVectorStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COLLECTION = "opencase_integration_test"
_DIMENSIONS = 768


def _fake_vector(dimensions: int = _DIMENSIONS) -> list[float]:
    return [0.1] * dimensions


def _make_embedding(
    document_id: str = "doc-1",
    chunk_index: int = 0,
    text: str = "hello world",
) -> EmbeddingResult:
    return EmbeddingResult(
        document_id=document_id,
        chunk_index=chunk_index,
        vector=_fake_vector(),
        text=text,
        metadata={},
    )


def _make_payload_metadata(**overrides: Any) -> dict[str, object]:
    defaults: dict[str, object] = {
        "firm_id": str(uuid.uuid4()),
        "matter_id": str(uuid.uuid4()),
        "client_id": str(uuid.uuid4()),
        "classification": "unclassified",
        "source": "government_production",
        "bates_number": None,
        "page_number": None,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qdrant_settings(qdrant_service: tuple[str, int]) -> QdrantSettings:
    host, port = qdrant_service
    return QdrantSettings(
        host=host,
        port=port,
        grpc_port=6334,
        collection=_COLLECTION,
        prefer_grpc=False,
        use_ssl=False,
        api_key=None,
    )


@pytest.fixture(scope="module")
def embedding_settings() -> EmbeddingSettings:
    return EmbeddingSettings(
        provider="ollama",
        model="nomic-embed-text",
        base_url="http://localhost:11434",
        dimensions=_DIMENSIONS,
        batch_size=100,
        request_timeout=120,
    )


@pytest.fixture(autouse=True, scope="module")
async def _ensure_collection(
    qdrant_settings: QdrantSettings,
) -> Any:
    """Create the test collection before tests and drop it after."""
    client = AsyncQdrantClient(url=qdrant_settings.url, api_key=qdrant_settings.api_key)
    with contextlib.suppress(Exception):
        await client.delete_collection(_COLLECTION)
    await client.create_collection(
        collection_name=_COLLECTION,
        vectors_config=models.VectorParams(
            size=_DIMENSIONS, distance=models.Distance.COSINE
        ),
    )
    yield
    await client.delete_collection(_COLLECTION)
    await client.close()


@pytest.fixture()
async def store(
    qdrant_settings: QdrantSettings,
    embedding_settings: EmbeddingSettings,
) -> Any:
    svc = QdrantVectorStore(qdrant_settings, embedding_settings)
    yield svc
    await svc.close()


@pytest.fixture()
async def _clean_collection(qdrant_settings: QdrantSettings) -> Any:
    """Wipe all points between tests for isolation."""
    yield
    client = AsyncQdrantClient(url=qdrant_settings.url, api_key=qdrant_settings.api_key)
    await client.delete(
        collection_name=_COLLECTION,
        points_selector=models.FilterSelector(filter=models.Filter(must=[])),
    )
    await client.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration()
@pytest.mark.asyncio()
@pytest.mark.usefixtures("_clean_collection")
class TestQdrantVectorStoreIntegration:
    async def test_upsert_and_scroll(self, store: QdrantVectorStore) -> None:
        embeddings = [_make_embedding(chunk_index=i) for i in range(3)]
        meta = _make_payload_metadata()

        count = await store.upsert_vectors(embeddings, meta)

        assert count == 3

        # Verify points exist via scroll
        client = store._client
        points, _ = await client.scroll(
            collection_name=_COLLECTION,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value="doc-1"),
                    )
                ]
            ),
            limit=100,
        )
        assert len(points) == 3

    async def test_upsert_idempotent(self, store: QdrantVectorStore) -> None:
        embeddings = [_make_embedding(chunk_index=i) for i in range(3)]
        meta = _make_payload_metadata()

        await store.upsert_vectors(embeddings, meta)
        await store.upsert_vectors(embeddings, meta)

        client = store._client
        points, _ = await client.scroll(
            collection_name=_COLLECTION,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value="doc-1"),
                    )
                ]
            ),
            limit=100,
        )
        # Same points overwritten, not duplicated
        assert len(points) == 3

    async def test_delete_by_document(self, store: QdrantVectorStore) -> None:
        embeddings = [_make_embedding(chunk_index=i) for i in range(3)]
        meta = _make_payload_metadata()

        await store.upsert_vectors(embeddings, meta)
        deleted = await store.delete_by_document("doc-1")

        assert deleted == 3

        # Verify deletion
        client = store._client
        points, _ = await client.scroll(
            collection_name=_COLLECTION,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value="doc-1"),
                    )
                ]
            ),
            limit=100,
        )
        assert len(points) == 0

    @pytest.mark.parametrize(
        "field",
        sorted(set(VectorPayload.__annotations__) - {"bates_number", "page_number"}),
    )
    async def test_payload_has_required_field(
        self, store: QdrantVectorStore, field: str
    ) -> None:
        emb = _make_embedding()
        meta = _make_payload_metadata(bates_number="GOV-001", page_number=42)

        await store.upsert_vectors([emb], meta)

        client = store._client
        points, _ = await client.scroll(
            collection_name=_COLLECTION,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value="doc-1"),
                    )
                ]
            ),
            limit=1,
            with_payload=True,
        )
        assert len(points) == 1
        assert field in points[0].payload

    async def test_bates_number_null(self, store: QdrantVectorStore) -> None:
        emb = _make_embedding()
        meta = _make_payload_metadata(bates_number=None)

        await store.upsert_vectors([emb], meta)

        client = store._client
        points, _ = await client.scroll(
            collection_name=_COLLECTION,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value="doc-1"),
                    )
                ]
            ),
            limit=1,
            with_payload=True,
        )
        assert len(points) == 1
        assert points[0].payload["bates_number"] is None

    async def test_bates_number_preserved(self, store: QdrantVectorStore) -> None:
        emb = _make_embedding()
        meta = _make_payload_metadata(bates_number="GOV-00142")

        await store.upsert_vectors([emb], meta)

        client = store._client
        points, _ = await client.scroll(
            collection_name=_COLLECTION,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value="doc-1"),
                    )
                ]
            ),
            limit=1,
            with_payload=True,
        )
        assert len(points) == 1
        assert points[0].payload["bates_number"] == "GOV-00142"
