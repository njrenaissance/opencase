"""Unit tests for the re-ingest endpoint and legal hold guard."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shared.models.enums import IngestionStatus, Role

from tests.conftest import FakeSession, api_client, auth_header
from tests.factories import make_document, make_user

_FIRM_ID = uuid.uuid4()
_MATTER_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# POST /documents/{document_id}/re-ingest
# ---------------------------------------------------------------------------


class TestReIngest:
    @pytest.mark.asyncio
    async def test_re_ingest_failed_document_returns_202(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        doc = make_document(
            firm_id=_FIRM_ID,
            matter_id=_MATTER_ID,
            uploaded_by=user.id,
            ingestion_status=IngestionStatus.failed,
        )
        fake = FakeSession()
        fake.add_result(doc)  # _get_document_with_access

        with patch("app.ingestion.get_ingestion_service") as mock_ingest:
            mock_ingest.return_value = MagicMock(process_document=AsyncMock())
            async with api_client(user, fake) as ac:
                resp = await ac.post(
                    f"/documents/{doc.id}/re-ingest",
                    headers=auth_header(user),
                )

        assert resp.status_code == 202
        data = resp.json()
        assert data["document_id"] == str(doc.id)
        assert data["ingestion_status"] == "pending"
        assert data["message"] == "Ingestion task submitted"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status",
        [
            IngestionStatus.pending,
            IngestionStatus.extracting,
            IngestionStatus.chunking,
            IngestionStatus.embedding,
            IngestionStatus.indexed,
        ],
    )
    async def test_re_ingest_non_failed_returns_409(
        self, status: IngestionStatus
    ) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        doc = make_document(
            firm_id=_FIRM_ID,
            matter_id=_MATTER_ID,
            uploaded_by=user.id,
            ingestion_status=status,
        )
        fake = FakeSession()
        fake.add_result(doc)

        async with api_client(user, fake) as ac:
            resp = await ac.post(
                f"/documents/{doc.id}/re-ingest",
                headers=auth_header(user),
            )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_re_ingest_not_found_returns_404(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        # No result queued → scalar_one_or_none returns None → 404

        async with api_client(user, fake) as ac:
            resp = await ac.post(
                f"/documents/{uuid.uuid4()}/re-ingest",
                headers=auth_header(user),
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_re_ingest_legal_hold_returns_409(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        doc = make_document(
            firm_id=_FIRM_ID,
            matter_id=_MATTER_ID,
            uploaded_by=user.id,
            ingestion_status=IngestionStatus.failed,
            legal_hold=True,
        )
        fake = FakeSession()
        fake.add_result(doc)

        async with api_client(user, fake) as ac:
            resp = await ac.post(
                f"/documents/{doc.id}/re-ingest",
                headers=auth_header(user),
            )

        assert resp.status_code == 409
        assert "legal hold" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_re_ingest_dispatch_failure_returns_500(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        doc = make_document(
            firm_id=_FIRM_ID,
            matter_id=_MATTER_ID,
            uploaded_by=user.id,
            ingestion_status=IngestionStatus.failed,
        )
        fake = FakeSession()
        fake.add_result(doc)

        with patch("app.ingestion.get_ingestion_service") as mock_ingest:
            mock_ingest.return_value = MagicMock(
                process_document=AsyncMock(side_effect=RuntimeError("broker down"))
            )
            async with api_client(user, fake) as ac:
                resp = await ac.post(
                    f"/documents/{doc.id}/re-ingest",
                    headers=auth_header(user),
                )

        assert resp.status_code == 500

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", [Role.paralegal, Role.investigator])
    async def test_re_ingest_forbidden_for_non_admin_attorney(self, role: Role) -> None:
        user = make_user(firm_id=_FIRM_ID, role=role)
        fake = FakeSession()

        async with api_client(user, fake) as ac:
            resp = await ac.post(
                f"/documents/{uuid.uuid4()}/re-ingest",
                headers=auth_header(user),
            )

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Legal hold guard in ingest_document task
# ---------------------------------------------------------------------------


class TestLegalHoldGuard:
    @pytest.mark.asyncio
    async def test_legal_hold_skips_ingestion(self) -> None:
        """When a document has legal_hold=True, _ingest returns skipped."""
        from app.workers.tasks.ingest_document import _ingest

        doc_id = str(uuid.uuid4())
        s3_key = f"firm/matter/{doc_id}/original.pdf"

        with patch(
            "app.workers.tasks.ingest_document._check_legal_hold",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await _ingest(doc_id, s3_key)

        assert result["status"] == "skipped"
        assert result["reason"] == "legal_hold"
        assert result["document_id"] == doc_id

    @pytest.mark.asyncio
    async def test_no_legal_hold_proceeds(self) -> None:
        """When legal_hold=False, ingestion proceeds (we mock the rest)."""
        from app.workers.tasks.ingest_document import _ingest

        doc_id = str(uuid.uuid4())
        s3_key = f"firm/matter/{doc_id}/original.pdf"

        with (
            patch(
                "app.workers.tasks.ingest_document._check_legal_hold",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.workers.tasks.ingest_document._update_ingestion_status",
                new_callable=AsyncMock,
            ),
            patch(
                "app.workers.tasks.ingest_document._run_extract",
                new_callable=AsyncMock,
            ) as mock_extract,
            patch(
                "app.workers.tasks.ingest_document._run_metadata_lookup",
                new_callable=AsyncMock,
                return_value={"firm_id": "f", "matter_id": "m", "client_id": "c"},
            ),
            patch(
                "app.workers.tasks.ingest_document._run_chunking",
                new_callable=AsyncMock,
                return_value=[{"text": "chunk"}],
            ),
            patch(
                "app.workers.tasks.ingest_document._run_embedding",
                new_callable=AsyncMock,
                return_value=1,
            ),
        ):
            mock_extract.return_value = MagicMock(text="hello world")
            result = await _ingest(doc_id, s3_key)

        assert result["status"] == "completed"
