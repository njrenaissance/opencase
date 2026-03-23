"""Tests for firm subcommands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from opencase_cli.main import app

from .conftest import FIRM_RESPONSE

_PATCH = "opencase_cli.commands.firms.get_client"


class TestGetFirm:
    def test_get_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.get_firm.return_value = FIRM_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["firm", "get"])
        assert result.exit_code == 0
        assert "Cora Firm" in result.output

    def test_get_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.get_firm.return_value = FIRM_RESPONSE
        with patch(_PATCH, return_value=mock_client):
            result = runner.invoke(app, ["firm", "get", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "Cora Firm"

    def test_not_authenticated(self, runner: CliRunner, tmp_opencase_dir: Path) -> None:
        result = runner.invoke(app, ["firm", "get"])
        assert result.exit_code == 1
