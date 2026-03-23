"""Tests for matter subcommands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from opencase_cli.main import app

from .conftest import (
    MATTER_ACCESS,
    MATTER_RESPONSE,
    MATTER_SUMMARY,
    REVOKE_RESPONSE,
)

_PATCH = "opencase_cli.commands.matters.get_client"
_MATTER_ID = "00000000-0000-0000-0000-000000000010"
_USER_ID = "00000000-0000-0000-0000-000000000001"


class TestListMatters:
    def test_list_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.list_matters.return_value = [MATTER_SUMMARY]
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["matter", "list"])
        assert result.exit_code == 0
        assert "People v. Smith" in result.output

    def test_list_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.list_matters.return_value = [MATTER_SUMMARY]
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["matter", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["name"] == "People v. Smith"


class TestGetMatter:
    def test_get_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.get_matter.return_value = MATTER_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["matter", "get", _MATTER_ID])
        assert result.exit_code == 0
        assert "People v. Smith" in result.output

    def test_get_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.get_matter.return_value = MATTER_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["matter", "get", _MATTER_ID, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "open"


class TestCreateMatter:
    def test_create_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.create_matter.return_value = MATTER_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "matter",
                    "create",
                    "--name",
                    "People v. Jones",
                    "--client-id",
                    _USER_ID,
                ],
            )
        assert result.exit_code == 0
        assert "created" in result.output


class TestUpdateMatter:
    def test_update_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.update_matter.return_value = MATTER_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(
                app,
                ["matter", "update", _MATTER_ID, "--name", "Renamed"],
            )
        assert result.exit_code == 0
        assert "updated" in result.output

    def test_update_no_fields(
        self,
        runner: CliRunner,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        result = runner.invoke(app, ["matter", "update", _MATTER_ID])
        assert result.exit_code == 1


class TestMatterAccess:
    def test_access_list(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.list_matter_access.return_value = [MATTER_ACCESS]
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["matter", "access-list", _MATTER_ID])
        assert result.exit_code == 0
        assert "user_id" in result.output

    def test_access_grant(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.grant_matter_access.return_value = MATTER_ACCESS
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "matter",
                    "access-grant",
                    _MATTER_ID,
                    "--user-id",
                    _USER_ID,
                ],
            )
        assert result.exit_code == 0
        assert "granted" in result.output

    def test_access_revoke(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.revoke_matter_access.return_value = REVOKE_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "matter",
                    "access-revoke",
                    _MATTER_ID,
                    "--user-id",
                    _USER_ID,
                ],
            )
        assert result.exit_code == 0

    def test_not_authenticated(self, runner: CliRunner, tmp_opencase_dir: Path) -> None:
        result = runner.invoke(app, ["matter", "list"])
        assert result.exit_code == 1
