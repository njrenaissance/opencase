"""Tests for task subcommands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from gideon_cli.main import app

from .conftest import (
    TASK_CANCEL_RESPONSE,
    TASK_RESPONSE,
    TASK_SUBMIT_RESPONSE,
    TASK_SUMMARY,
)

_PATCH = "gideon_cli.commands.tasks.get_client"
_TASK_ID = "00000000-0000-0000-0000-000000000030"


class TestListTasks:
    def test_list_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.list_tasks.return_value = [TASK_SUMMARY]
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["task", "list"])
        assert result.exit_code == 0
        assert "ping" in result.output

    def test_list_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.list_tasks.return_value = [TASK_SUMMARY]
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["task", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["task_name"] == "ping"


class TestGetTask:
    def test_get_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.get_task.return_value = TASK_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["task", "get", _TASK_ID])
        assert result.exit_code == 0
        assert "pong" in result.output

    def test_get_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.get_task.return_value = TASK_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["task", "get", _TASK_ID, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "SUCCESS"


class TestSubmitTask:
    def test_submit_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.submit_task.return_value = TASK_SUBMIT_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["task", "submit", "--task-name", "ping"])
        assert result.exit_code == 0
        assert "submitted" in result.output

    def test_submit_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.submit_task.return_value = TASK_SUBMIT_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(
                app, ["task", "submit", "--task-name", "ping", "--json"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "task_id" in data


class TestCancelTask:
    def test_cancel_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.cancel_task.return_value = TASK_CANCEL_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["task", "cancel", _TASK_ID])
        assert result.exit_code == 0
        assert "revoked" in result.output
