"""Tests for document subcommands (upload + bulk-ingest)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from gideon.exceptions import GideonError
from shared.models.document import (
    DocumentSummary,
    DuplicateCheckResponse,
    ReIngestResponse,
)
from shared.models.enums import IngestionStatus
from typer.testing import CliRunner

from gideon_cli.main import app

from .conftest import DOCUMENT_RESPONSE, DOCUMENT_SUMMARY

_PATCH_CLIENT = "gideon_cli.commands.documents.get_client"
_PATCH_HASH = "gideon_cli.commands.documents.hash_file"
_MATTER_ID = "00000000-0000-0000-0000-000000000010"
_NOT_DUP = DuplicateCheckResponse(exists=False, document_id=None)
_IS_DUP = DuplicateCheckResponse(
    exists=True, document_id="00000000-0000-0000-0000-000000000040"
)


def _make_files(tmp_path: Path, names: list[str]) -> list[Path]:
    """Create empty files in tmp_path and return their paths."""
    paths = []
    for name in names:
        p = tmp_path / name
        p.write_bytes(b"fake content")
        paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# document upload
# ---------------------------------------------------------------------------


class TestUploadDocument:
    def test_upload_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
        tmp_path: Path,
    ) -> None:
        f = tmp_path / "brief.pdf"
        f.write_bytes(b"%PDF-1.4 fake")
        mock_client.upload_document.return_value = DOCUMENT_RESPONSE
        with patch(_PATCH_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                ["document", "upload", str(f), "--matter-id", _MATTER_ID],
            )
        assert result.exit_code == 0
        assert "uploaded" in result.output.lower()
        mock_client.upload_document.assert_called_once()
        call_kw = mock_client.upload_document.call_args.kwargs
        assert call_kw["matter_id"] == _MATTER_ID

    def test_upload_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
        tmp_path: Path,
    ) -> None:
        f = tmp_path / "brief.pdf"
        f.write_bytes(b"%PDF-1.4 fake")
        mock_client.upload_document.return_value = DOCUMENT_RESPONSE
        with patch(_PATCH_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                ["document", "upload", str(f), "--matter-id", _MATTER_ID, "--json"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["filename"] == "evidence.pdf"


# ---------------------------------------------------------------------------
# document bulk-ingest
# ---------------------------------------------------------------------------


class TestBulkIngest:
    def test_dry_run(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
        tmp_path: Path,
    ) -> None:
        _make_files(tmp_path, ["a.pdf", "b.txt", "c.jpg"])
        with patch(_PATCH_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "document",
                    "bulk-ingest",
                    str(tmp_path),
                    "--matter-id",
                    _MATTER_ID,
                    "--dry-run",
                ],
            )
        assert result.exit_code == 0
        assert "3" in result.output
        # No upload calls should have been made (only get_ingestion_config)
        mock_client.upload_document.assert_not_called()

    def test_upload_all_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
        tmp_path: Path,
    ) -> None:
        _make_files(tmp_path, ["a.pdf", "b.txt"])
        mock_client.upload_document.return_value = DOCUMENT_RESPONSE
        mock_client.check_duplicate.return_value = _NOT_DUP
        with (
            patch(_PATCH_CLIENT, return_value=mock_client),
            patch(_PATCH_HASH, return_value="f" * 64),
        ):
            result = runner.invoke(
                app,
                ["document", "bulk-ingest", str(tmp_path), "--matter-id", _MATTER_ID],
            )
        assert result.exit_code == 0
        assert "2" in result.output and "uploaded" in result.output
        assert mock_client.upload_document.call_count == 2  # noqa: PLR2004

    def test_skip_duplicates(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
        tmp_path: Path,
    ) -> None:
        _make_files(tmp_path, ["a.pdf"])
        mock_client.check_duplicate.return_value = _IS_DUP
        with (
            patch(_PATCH_CLIENT, return_value=mock_client),
            patch(_PATCH_HASH, return_value="f" * 64),
        ):
            result = runner.invoke(
                app,
                ["document", "bulk-ingest", str(tmp_path), "--matter-id", _MATTER_ID],
            )
        assert result.exit_code == 0
        assert "skipped" in result.output.lower()
        mock_client.upload_document.assert_not_called()

    def test_partial_failure(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
        tmp_path: Path,
    ) -> None:
        _make_files(tmp_path, ["a.pdf", "b.txt"])
        mock_client.check_duplicate.return_value = _NOT_DUP
        mock_client.upload_document.side_effect = [
            DOCUMENT_RESPONSE,
            GideonError("Server error", status_code=500),
        ]
        with (
            patch(_PATCH_CLIENT, return_value=mock_client),
            patch(_PATCH_HASH, return_value="f" * 64),
        ):
            result = runner.invoke(
                app,
                ["document", "bulk-ingest", str(tmp_path), "--matter-id", _MATTER_ID],
            )
        assert result.exit_code == 1
        assert "1" in result.output and "uploaded" in result.output
        assert "1" in result.output and "failed" in result.output

    def test_no_recursive(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
        tmp_path: Path,
    ) -> None:
        _make_files(tmp_path, ["top.pdf"])
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.pdf").write_bytes(b"nested")
        mock_client.upload_document.return_value = DOCUMENT_RESPONSE
        mock_client.check_duplicate.return_value = _NOT_DUP
        with (
            patch(_PATCH_CLIENT, return_value=mock_client),
            patch(_PATCH_HASH, return_value="f" * 64),
        ):
            result = runner.invoke(
                app,
                [
                    "document",
                    "bulk-ingest",
                    str(tmp_path),
                    "--matter-id",
                    _MATTER_ID,
                    "--no-recursive",
                ],
            )
        assert result.exit_code == 0
        assert mock_client.upload_document.call_count == 1

    def test_unsupported_extensions_filtered(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
        tmp_path: Path,
    ) -> None:
        _make_files(tmp_path, ["good.pdf", "bad.xyz", "bad.exe"])
        mock_client.upload_document.return_value = DOCUMENT_RESPONSE
        mock_client.check_duplicate.return_value = _NOT_DUP
        with (
            patch(_PATCH_CLIENT, return_value=mock_client),
            patch(_PATCH_HASH, return_value="f" * 64),
        ):
            result = runner.invoke(
                app,
                ["document", "bulk-ingest", str(tmp_path), "--matter-id", _MATTER_ID],
            )
        assert result.exit_code == 0
        assert mock_client.upload_document.call_count == 1

    def test_empty_directory(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
        tmp_path: Path,
    ) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with patch(_PATCH_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                ["document", "bulk-ingest", str(empty), "--matter-id", _MATTER_ID],
            )
        assert result.exit_code == 0
        assert "no supported files" in result.output.lower()

    def test_json_output(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
        tmp_path: Path,
    ) -> None:
        _make_files(tmp_path, ["a.pdf", "b.txt"])
        mock_client.check_duplicate.side_effect = [_NOT_DUP, _IS_DUP]
        mock_client.upload_document.return_value = DOCUMENT_RESPONSE
        with (
            patch(_PATCH_CLIENT, return_value=mock_client),
            patch(_PATCH_HASH, return_value="f" * 64),
        ):
            result = runner.invoke(
                app,
                [
                    "document",
                    "bulk-ingest",
                    str(tmp_path),
                    "--matter-id",
                    _MATTER_ID,
                    "--json",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2  # noqa: PLR2004
        statuses = {r["status"] for r in data}
        assert "uploaded" in statuses
        assert "skipped" in statuses


# ---------------------------------------------------------------------------
# document re-ingest
# ---------------------------------------------------------------------------


class TestReIngest:
    def test_re_ingest_single_document(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        doc_id = "00000000-0000-0000-0000-000000000040"
        re_ingest_response = ReIngestResponse(
            document_id=doc_id,
            ingestion_status=IngestionStatus.pending,
            message="Re-ingestion queued.",
        )
        mock_client.re_ingest_document.return_value = re_ingest_response

        with patch(_PATCH_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                ["document", "re-ingest", doc_id],
            )

        assert result.exit_code == 0
        mock_client.re_ingest_document.assert_called_once_with(doc_id)

    def test_re_ingest_all_failed(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        failed_doc = DocumentSummary(
            **{
                **DOCUMENT_SUMMARY.model_dump(),
                "ingestion_status": IngestionStatus.failed,
            }
        )
        # Simulate pagination: first call returns one doc, second call returns empty
        mock_client.list_documents.side_effect = [[failed_doc], []]
        mock_client.re_ingest_document.return_value = ReIngestResponse(
            document_id=str(failed_doc.id),
            ingestion_status=IngestionStatus.pending,
            message="Re-ingestion queued.",
        )

        with patch(_PATCH_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                ["document", "re-ingest", "--all-failed"],
            )

        assert result.exit_code == 0
        mock_client.re_ingest_document.assert_called_once_with(str(failed_doc.id))

    def test_re_ingest_invalid_uuid(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        with patch(_PATCH_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                ["document", "re-ingest", "not-a-uuid"],
            )

        assert result.exit_code == 1
        assert "not a valid UUID" in result.output

    def test_re_ingest_no_args_errors(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        with patch(_PATCH_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                ["document", "re-ingest"],
            )

        assert result.exit_code == 1

    def test_re_ingest_both_args_errors(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        with patch(_PATCH_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "document",
                    "re-ingest",
                    "00000000-0000-0000-0000-000000000040",
                    "--all-failed",
                ],
            )

        assert result.exit_code == 1

    def test_re_ingest_all_failed_none_found(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        # Simulate server-side filtering: no failed documents
        # First call returns empty list (no failed docs), so no second pagination call
        mock_client.list_documents.return_value = []

        with patch(_PATCH_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                ["document", "re-ingest", "--all-failed"],
            )

        assert result.exit_code == 0
        assert "No failed documents found" in result.output

    def test_re_ingest_all_failed_none_found_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        # Simulate pagination: first call returns empty list
        mock_client.list_documents.return_value = []

        with patch(_PATCH_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                ["document", "re-ingest", "--all-failed", "--json"],
            )

        assert result.exit_code == 0
        assert json.loads(result.output) == []

    def test_re_ingest_all_failed_partial_failure(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        failed_doc_1 = DocumentSummary(
            **{
                **DOCUMENT_SUMMARY.model_dump(),
                "id": "00000000-0000-0000-0000-000000000041",
                "ingestion_status": IngestionStatus.failed,
            }
        )
        failed_doc_2 = DocumentSummary(
            **{
                **DOCUMENT_SUMMARY.model_dump(),
                "id": "00000000-0000-0000-0000-000000000042",
                "ingestion_status": IngestionStatus.failed,
            }
        )
        # Simulate pagination: first call returns two docs, second call returns empty
        mock_client.list_documents.side_effect = [[failed_doc_1, failed_doc_2], []]
        mock_client.re_ingest_document.side_effect = [
            ReIngestResponse(
                document_id=str(failed_doc_1.id),
                ingestion_status=IngestionStatus.pending,
                message="Re-ingestion queued.",
            ),
            GideonError("Server error", status_code=500),
        ]

        with patch(_PATCH_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                ["document", "re-ingest", "--all-failed"],
            )

        assert result.exit_code == 1
        assert "1" in result.output and "queued" in result.output
        assert "1" in result.output and "failed" in result.output
