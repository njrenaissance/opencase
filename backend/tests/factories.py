"""Shared test factories for backend tests.

Plain functions (not fixtures) because they accept parameters.
Import by name: ``from tests.factories import make_chunk``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.models.enums import (
    Classification,
    DocumentSource,
    IngestionStatus,
    MatterStatus,
    Role,
    TaskState,
)

if TYPE_CHECKING:
    from app.core.config import ChunkingSettings, EmbeddingSettings, QdrantSettings
    from app.embedding.models import EmbeddingResult

from app.db.models.document import Document
from app.db.models.firm import Firm
from app.db.models.matter import Matter
from app.db.models.matter_access import MatterAccess
from app.db.models.task_submission import TaskSubmission
from app.db.models.user import User


def make_firm(**kwargs: object) -> Firm:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "Test Firm",
    }
    defaults.update(kwargs)
    return Firm(**defaults)


def make_user(**kwargs: object) -> User:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "firm_id": uuid.uuid4(),
        "email": f"{uuid.uuid4()}@example.com",
        "hashed_password": "hashed-in-test",  # noqa: S106
        "first_name": "Test",
        "last_name": "User",
        "middle_initial": None,
        "role": Role.attorney,
        "is_active": True,
        "totp_enabled": False,
        "totp_secret": None,
        "totp_verified_at": None,
        "failed_login_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return User(**defaults)


def make_matter(**kwargs: object) -> Matter:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "firm_id": uuid.uuid4(),
        "name": "Test Matter",
        "client_id": uuid.uuid4(),
        "status": MatterStatus.open,
        "legal_hold": False,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return Matter(**defaults)


def make_task_submission(**kwargs: object) -> TaskSubmission:
    defaults: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "firm_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "task_name": "ping",
        "args_json": "[]",
        "kwargs_json": "{}",
        "status": TaskState.pending,
        "submitted_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return TaskSubmission(**defaults)


def make_document(**kwargs: object) -> Document:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "firm_id": uuid.uuid4(),
        "matter_id": uuid.uuid4(),
        "filename": "test.pdf",
        "file_hash": "a" * 64,
        "content_type": "application/pdf",
        "size_bytes": 1024,
        "source": DocumentSource.defense,
        "classification": Classification.unclassified,
        "ingestion_status": IngestionStatus.pending,
        "bates_number": None,
        "legal_hold": False,
        "uploaded_by": uuid.uuid4(),
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return Document(**defaults)


def make_matter_access(**kwargs: object) -> MatterAccess:
    defaults: dict[str, object] = {
        "user_id": uuid.uuid4(),
        "matter_id": uuid.uuid4(),
        "view_work_product": False,
        "assigned_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return MatterAccess(**defaults)


# ---------------------------------------------------------------------------
# Embedding / vectorstore / pipeline factories
# ---------------------------------------------------------------------------


def fake_vector(dimensions: int = 768) -> list[float]:
    """Return a deterministic embedding vector for testing."""
    return [0.1] * dimensions


def make_chunk(
    document_id: str = "doc-1",
    chunk_index: int = 0,
    text: str = "hello world",
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a chunk dict matching ChunkResult.to_dict() shape."""
    return {
        "document_id": document_id,
        "chunk_index": chunk_index,
        "text": text,
        "char_start": 0,
        "char_end": len(text),
        "metadata": metadata or {},
    }


def make_embedding_result(
    document_id: str = "doc-1",
    chunk_index: int = 0,
    text: str = "hello world",
    dimensions: int = 768,
    metadata: dict[str, object] | None = None,
) -> EmbeddingResult:
    """Build an EmbeddingResult with a fake vector."""
    from app.embedding.models import EmbeddingResult as EmbResult

    return EmbResult(
        document_id=document_id,
        chunk_index=chunk_index,
        vector=fake_vector(dimensions),
        text=text,
        metadata=metadata or {},
    )


def make_payload_metadata(**overrides: Any) -> dict[str, object]:
    """Build a Qdrant payload metadata dict with sensible defaults."""
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


def make_chunking_settings(**overrides: Any) -> ChunkingSettings:
    """Build ChunkingSettings with sensible defaults."""
    from app.core.config import ChunkingSettings as CSettings

    defaults: dict[str, Any] = {
        "strategy": "recursive",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "separators": ["\n\n", "\n", ". ", " ", ""],
    }
    defaults.update(overrides)
    return CSettings(**defaults)


def make_embedding_settings(**overrides: Any) -> EmbeddingSettings:
    """Build EmbeddingSettings with sensible defaults."""
    from app.core.config import EmbeddingSettings as EmbSettings

    defaults: dict[str, Any] = {
        "provider": "ollama",
        "model": "nomic-embed-text",
        "base_url": "http://ollama:11434",
        "dimensions": 768,
        "batch_size": 100,
        "request_timeout": 120,
    }
    defaults.update(overrides)
    return EmbSettings(**defaults)


def make_qdrant_settings(**overrides: Any) -> QdrantSettings:
    """Build QdrantSettings with sensible defaults."""
    from app.core.config import QdrantSettings as QdSettings

    defaults: dict[str, Any] = {
        "host": "localhost",
        "port": 6333,
        "grpc_port": 6334,
        "collection": "gideon_test",
        "prefer_grpc": False,
        "use_ssl": False,
        "api_key": None,
    }
    defaults.update(overrides)
    return QdSettings(**defaults)
