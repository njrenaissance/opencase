"""Tests for document subcommands (upload + bulk-ingest)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from gideon.exceptions import GideonError
from shared.models.document import DuplicateCheckResponse
from typer.testing import CliRunner

from gideon_cli.main import app

from .conftest import DOCUMENT_RESPONSE

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
