"""Smoke tests for Celery app and task registration.

These catch import errors and misconfiguration before integration tests
spin up the full Docker stack.
"""

from celery import Celery

from app.core.config import settings


def test_celery_app_is_importable():
    """Celery app module loads without error."""
    from app.workers import celery_app

    assert isinstance(celery_app, Celery)


def test_celery_broker_url_matches_settings():
    from app.workers import celery_app

    assert celery_app.conf.broker_url == settings.celery.broker_url


def test_celery_result_backend_matches_settings():
    from app.workers import celery_app

    assert celery_app.conf.result_backend == settings.celery.result_backend


def test_ping_task_is_registered():
    """Task module is discoverable and registers with the Celery app."""
    # Import the task module to trigger shared_task registration.
    import app.workers.tasks.ping  # noqa: F401
    from app.workers import celery_app

    assert "opencase.ping" in celery_app.tasks


def test_ping_task_returns_pong():
    """Calling the task function directly returns 'pong'."""
    from app.workers.tasks.ping import ping

    assert ping() == "pong"


# ---------------------------------------------------------------------------
# extract_document task
# ---------------------------------------------------------------------------


def test_extract_document_task_is_registered():
    import app.workers.tasks.extract_document  # noqa: F401
    from app.workers import celery_app

    assert "opencase.extract_document" in celery_app.tasks


def test_extract_document_in_task_registry():
    from app.workers.registry import TASK_REGISTRY

    assert TASK_REGISTRY["extract_document"] == "opencase.extract_document"


def test_extract_document_task_returns_dict():
    """Mock S3 + extraction service and call the task function directly."""
    from unittest.mock import AsyncMock, patch

    from app.extraction.models import ExtractionResult

    mock_result = ExtractionResult(
        text="hello",
        content_type="text/plain",
        metadata={},
        ocr_applied=False,
        language="en",
    )

    mock_storage = AsyncMock()
    mock_storage.download_document.return_value = (b"data", "text/plain")

    mock_extraction = AsyncMock()
    mock_extraction.extract_text.return_value = mock_result

    with (
        patch("app.storage.get_storage_service", return_value=mock_storage),
        patch("app.extraction.get_extraction_service", return_value=mock_extraction),
    ):
        from app.workers.tasks.extract_document import extract_document

        result = extract_document("doc-id", "firm/matter/doc/original.pdf")

    assert result["text"] == "hello"
    assert result["content_type"] == "text/plain"
    assert result["ocr_applied"] is False


# ---------------------------------------------------------------------------
# ingest_document task (orchestration)
# ---------------------------------------------------------------------------


def test_ingest_document_task_is_registered():
    import app.workers.tasks.ingest_document  # noqa: F401
    from app.workers import celery_app

    assert "opencase.ingest_document" in celery_app.tasks


def test_ingest_document_full_pipeline():
    """ingest_document should extract, chunk, embed, and upsert to Qdrant."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.chunking.models import ChunkResult
    from app.embedding.models import EmbeddingResult
    from app.extraction.models import ExtractionResult

    mock_result = ExtractionResult(
        text="extracted content",
        content_type="application/pdf",
        metadata={"author": "test"},
        ocr_applied=False,
        language="en",
    )

    mock_storage = AsyncMock()
    mock_storage.download_document.return_value = (b"pdf bytes", "application/pdf")

    mock_extraction = AsyncMock()
    mock_extraction.extract_text.return_value = mock_result

    mock_chunking = MagicMock()
    mock_chunking.chunk_text.return_value = [
        ChunkResult(
            document_id="doc-1",
            chunk_index=0,
            text="extracted content",
            char_start=0,
            char_end=17,
            metadata={},
        ),
    ]

    mock_embedding_svc = AsyncMock()
    mock_embedding_svc.embed_chunks.return_value = [
        EmbeddingResult(
            document_id="doc-1",
            chunk_index=0,
            vector=[0.1] * 768,
            text="extracted content",
            metadata={},
        ),
    ]

    mock_vectorstore = AsyncMock()
    mock_vectorstore.upsert_vectors.return_value = 1
    mock_vectorstore.close = AsyncMock()

    # Mock the DB session to return document + matter
    mock_doc = SimpleNamespace(
        firm_id="firm-1",
        matter_id="matter-1",
        classification="unclassified",
        source="defense",
        bates_number=None,
    )
    mock_matter = SimpleNamespace(client_id="client-1")

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[mock_doc, mock_matter])
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_engine = AsyncMock()
    mock_engine.dispose = AsyncMock()

    s3_key = "firm-1/matter-1/doc-1/original.pdf"

    with (
        patch("app.storage.get_storage_service", return_value=mock_storage),
        patch(
            "app.extraction.get_extraction_service",
            return_value=mock_extraction,
        ),
        patch(
            "app.chunking.get_chunking_service",
            return_value=mock_chunking,
        ),
        patch(
            "app.workers.tasks.ingest_document.EmbeddingService",
            return_value=mock_embedding_svc,
        ),
        patch(
            "app.workers.tasks.ingest_document.QdrantVectorStore",
            return_value=mock_vectorstore,
        ),
        patch(
            "app.workers.tasks.ingest_document.create_async_engine",
            return_value=mock_engine,
        ),
        patch(
            "app.workers.tasks.ingest_document.AsyncSession",
            return_value=mock_session_ctx,
        ),
    ):
        from app.workers.tasks.ingest_document import ingest_document

        result = ingest_document("doc-1", s3_key)

    assert result["status"] == "completed"
    assert result["document_id"] == "doc-1"
    assert result["chunk_count"] == 1
    assert result["point_count"] == 1

    # Verify extraction was called
    mock_extraction.extract_text.assert_awaited_once_with(
        b"pdf bytes",
        "original.pdf",
        "application/pdf",
    )

    # Verify extracted.json was uploaded to S3
    upload_calls = mock_storage.upload_json.call_args_list
    assert any(
        c.kwargs["key"] == "firm-1/matter-1/doc-1/extracted.json" for c in upload_calls
    )

    # Verify chunks.json was uploaded to S3
    assert any(
        c.kwargs["key"] == "firm-1/matter-1/doc-1/chunks.json" for c in upload_calls
    )

    # Verify embedding + upsert were called
    mock_embedding_svc.embed_chunks.assert_awaited_once()
    mock_vectorstore.upsert_vectors.assert_awaited_once()
