"""Tests for health and ready commands."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from opencase_cli.main import app

from .conftest import HEALTH_RESPONSE, READINESS_DEGRADED, READINESS_RESPONSE

_PATCH_GET_CLIENT = "opencase_cli.commands.health.get_client"


class TestHealth:
    def test_health_success(
        self, runner: CliRunner, mock_client: Any, tmp_opencase_dir: Any
    ) -> None:
        mock_client.health.return_value = HEALTH_RESPONSE
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "ok" in result.output

    def test_health_json(
        self, runner: CliRunner, mock_client: Any, tmp_opencase_dir: Any
    ) -> None:
        mock_client.health.return_value = HEALTH_RESPONSE
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["app"] == "opencase"

    def test_health_connection_error(
        self, runner: CliRunner, mock_client: Any, tmp_opencase_dir: Any
    ) -> None:
        import httpx

        mock_client.health.side_effect = httpx.ConnectError("refused")
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 1


class TestReady:
    def test_ready_success(
        self, runner: CliRunner, mock_client: Any, tmp_opencase_dir: Any
    ) -> None:
        mock_client.readiness.return_value = READINESS_RESPONSE
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(app, ["ready"])
        assert result.exit_code == 0
        assert "ok" in result.output

    def test_ready_json(
        self, runner: CliRunner, mock_client: Any, tmp_opencase_dir: Any
    ) -> None:
        mock_client.readiness.return_value = READINESS_RESPONSE
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(app, ["ready", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_ready_degraded_exits_1(
        self, runner: CliRunner, mock_client: Any, tmp_opencase_dir: Any
    ) -> None:
        mock_client.readiness.return_value = READINESS_DEGRADED
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(app, ["ready"])
        assert result.exit_code == 1
