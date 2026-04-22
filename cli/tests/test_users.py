"""Tests for user subcommands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from gideon_cli.main import app

from .conftest import USER_RESPONSE, USER_SUMMARY

_PATCH = "gideon_cli.commands.users.get_client"


class TestListUsers:
    def test_list_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.list_users.return_value = [USER_SUMMARY]
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["user", "list"])
        assert result.exit_code == 0
        assert "user@firm.com" in result.output

    def test_list_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.list_users.return_value = [USER_SUMMARY]
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["user", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["email"] == "user@firm.com"


class TestGetUser:
    def test_get_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.get_user.return_value = USER_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(
                app, ["user", "get", "00000000-0000-0000-0000-000000000001"]
            )
        assert result.exit_code == 0
        assert "user@firm.com" in result.output

    def test_get_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.get_user.return_value = USER_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(
                app,
                ["user", "get", "00000000-0000-0000-0000-000000000001", "--json"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["role"] == "attorney"


class TestCreateUser:
    @pytest.mark.parametrize(
        "extra_args,expected_middle_initial",
        [
            ([], None),
            (["--middle-initial", "B"], "B"),
        ],
        ids=["without_middle_initial", "with_middle_initial"],
    )
    def test_create_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
        extra_args: list[str],
        expected_middle_initial: str | None,
    ) -> None:
        mock_client.create_user.return_value = USER_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "user",
                    "create",
                    "--email",
                    "new@firm.com",
                    "--password",
                    "secretpass123",
                    "--first-name",
                    "Jane",
                    "--last-name",
                    "Doe",
                    "--role",
                    "attorney",
                    *extra_args,
                ],
            )
        assert result.exit_code == 0
        assert "created" in result.output
        _, kwargs = mock_client.create_user.call_args
        assert kwargs.get("middle_initial") == expected_middle_initial


class TestUpdateUser:
    @pytest.mark.parametrize(
        "extra_args,expected_fields",
        [
            ([], {"first_name": "Janet"}),
            (["--middle-initial", "C"], {"first_name": "Janet", "middle_initial": "C"}),
        ],
        ids=["without_middle_initial", "with_middle_initial"],
    )
    def test_update_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
        extra_args: list[str],
        expected_fields: dict,
    ) -> None:
        mock_client.update_user.return_value = USER_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "user",
                    "update",
                    "00000000-0000-0000-0000-000000000001",
                    "--first-name",
                    "Janet",
                    *extra_args,
                ],
            )
        assert result.exit_code == 0
        assert "updated" in result.output
        _, kwargs = mock_client.update_user.call_args
        for field, value in expected_fields.items():
            assert kwargs.get(field) == value

    def test_update_no_fields(
        self,
        runner: CliRunner,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        result = runner.invoke(
            app,
            ["user", "update", "00000000-0000-0000-0000-000000000001"],
        )
        assert result.exit_code == 1

    def test_not_authenticated(self, runner: CliRunner, tmp_gideon_dir: Path) -> None:
        result = runner.invoke(app, ["user", "list"])
        assert result.exit_code == 1
