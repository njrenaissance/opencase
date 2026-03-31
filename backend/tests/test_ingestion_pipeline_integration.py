"""End-to-end integration test for the full ingestion pipeline.

Exercises: upload to MinIO → extract via Tika → chunk → embed via Ollama →
upsert to Qdrant. Requires the full Docker stack (``pytest -m integration``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from qdrant_client import QdrantClient, models
from shared.models.enums import Role
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.auth import hash_password
from app.core.config import settings
from app.db.models.document import Document
from app.db.models.firm import Firm
from app.db.models.matter import Matter
from app.db.models.matter_access import MatterAccess
from app.db.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PASSWORD = "TestPassword123!"  # noqa: S105
_COLLECTION = "opencase_test"


def _sync_db_url() -> str:
    """Convert the async DB URL to a sync one for test setup."""
    return settings.db.url.replace("+asyncpg", "")


def _login(base_url: str, email: str, password: str) -> dict[str, str]:
    resp = httpx.post(
        f"{base_url}/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    token = data.get("access_token") or data.get("mfa_token")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def seed_pipeline(
    postgres_service: Any,
) -> Any:
    """Seed a firm, user, matter for the pipeline test. Yields IDs dict."""
    engine = create_engine(_sync_db_url())
    now = datetime.now(UTC)
    firm_id = uuid.uuid4()
    user_id = uuid.uuid4()
    matter_id = uuid.uuid4()
    client_id = uuid.uuid4()

    with Session(engine) as session:
        session.add(Firm(id=firm_id, name="Pipeline Test Firm"))
        session.flush()

        session.add(
            User(
                id=user_id,
                firm_id=firm_id,
                email="pipeline@testfirm.com",
                hashed_password=hash_password(_PASSWORD),
                first_name="Test",
                last_name="User",
                role=Role.attorney,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()

        session.add(
            Matter(
                id=matter_id,
                firm_id=firm_id,
                name="People v. Pipeline",
                client_id=client_id,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()

        session.add(MatterAccess(user_id=user_id, matter_id=matter_id, assigned_at=now))
        session.commit()

    yield {
        "firm_id": firm_id,
        "user_id": user_id,
        "matter_id": matter_id,
        "client_id": client_id,
        "email": "pipeline@testfirm.com",
        "password": _PASSWORD,
    }

    # Teardown
    with Session(engine) as session:
        session.execute(delete(Document).where(Document.matter_id == matter_id))
        session.execute(delete(MatterAccess).where(MatterAccess.matter_id == matter_id))
        session.execute(delete(Matter).where(Matter.id == matter_id))
        session.execute(delete(User).where(User.id == user_id))
        session.execute(delete(Firm).where(Firm.id == firm_id))
        session.commit()

    engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration()
class TestIngestionPipelineEndToEnd:
    """Upload a document via the API and verify vectors land in Qdrant."""

    def test_upload_triggers_full_pipeline(
        self,
        fastapi_service: str,
        qdrant_service: tuple[str, int],
        ollama_service: tuple[str, int],
        seed_pipeline: dict[str, Any],
    ) -> None:
        base_url = fastapi_service
        seed = seed_pipeline
        qdrant_host, qdrant_port = qdrant_service

        # Login
        headers = _login(base_url, seed["email"], seed["password"])

        # Upload a text document (plain text so Tika extraction is fast)
        file_content = (
            b"The defendant was observed near the scene on January 15th. "
            b"Officer Martinez filed the initial report noting witness "
            b"testimony from three bystanders. The surveillance footage "
            b"from the nearby convenience store was also collected as "
            b"evidence. Defense counsel has requested all Brady material "
            b"related to this incident."
        )

        resp = httpx.post(
            f"{base_url}/documents/",
            headers=headers,
            files={"file": ("evidence_report.txt", file_content, "text/plain")},
            data={
                "matter_id": str(seed["matter_id"]),
                "source": "government_production",
                "classification": "unclassified",
                "bates_number": "GOV-00001",
            },
            timeout=30,
        )
        assert resp.status_code == 201, resp.text
        doc = resp.json()
        doc_id = doc["id"]

        # Wait for the Celery worker to process the full pipeline.
        # Poll the task status endpoint until completion or timeout.
        import time

        deadline = time.monotonic() + 120  # 2 minute timeout
        task_status = None
        while time.monotonic() < deadline:
            # Check if vectors have appeared in Qdrant
            qdrant = QdrantClient(host=qdrant_host, port=qdrant_port, timeout=5)
            try:
                points, _ = qdrant.scroll(
                    collection_name=_COLLECTION,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=doc_id),
                            )
                        ]
                    ),
                    limit=100,
                    with_payload=True,
                    with_vectors=True,
                )
                if len(points) > 0:
                    task_status = "completed"
                    break
            finally:
                qdrant.close()

            time.sleep(2)

        assert task_status == "completed", (
            f"Pipeline did not complete within 120s for document {doc_id}"
        )

        # Verify vectors in Qdrant
        assert len(points) >= 1, "Expected at least 1 vector in Qdrant"

        # Verify payload has all required fields
        payload = points[0].payload
        assert payload["firm_id"] == str(seed["firm_id"])
        assert payload["matter_id"] == str(seed["matter_id"])
        assert payload["client_id"] == str(seed["client_id"])
        assert payload["document_id"] == doc_id
        assert payload["classification"] == "unclassified"
        assert payload["source"] == "government_production"
        assert payload["bates_number"] == "GOV-00001"
        assert "chunk_index" in payload

        # Verify vectors are non-empty 768-dimensional
        vector = points[0].vector
        assert len(vector) == 768
        assert any(v != 0.0 for v in vector)
