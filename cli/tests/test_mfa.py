"""Tests for MFA subcommands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from opencase_cli.main import app

from .conftest import MFA_DISABLED, MFA_ENABLED, MFA_SETUP

_PATCH_GET_CLIENT = "opencase_cli.commands.mfa.get_client"


class TestMfaSetup:
    def test_setup_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.mfa_setup.return_value = MFA_SETUP
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(app, ["mfa", "setup"])
        assert result.exit_code == 0
        assert "JBSWY3DPEHPK3PXP" in result.output

    def test_setup_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.mfa_setup.return_value = MFA_SETUP
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(app, ["mfa", "setup", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["totp_secret"] == "JBSWY3DPEHPK3PXP"

    def test_setup_not_authenticated(
        self, runner: CliRunner, tmp_opencase_dir: Path
    ) -> None:
        result = runner.invoke(app, ["mfa", "setup"])
        assert result.exit_code == 1


class TestMfaConfirm:
    def test_confirm_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.mfa_confirm.return_value = MFA_ENABLED
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(app, ["mfa", "confirm", "--totp-code", "123456"])
        assert result.exit_code == 0
        assert "MFA enabled" in result.output

    def test_confirm_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.mfa_confirm.return_value = MFA_ENABLED
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app, ["mfa", "confirm", "--totp-code", "123456", "--json"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["enabled"] is True


class TestMfaDisable:
    def test_disable_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.mfa_disable.return_value = MFA_DISABLED
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(app, ["mfa", "disable", "--totp-code", "123456"])
        assert result.exit_code == 0
        assert "MFA disabled" in result.output

    def test_disable_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_opencase_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.mfa_disable.return_value = MFA_DISABLED
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app, ["mfa", "disable", "--totp-code", "123456", "--json"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["enabled"] is False

    def test_disable_not_authenticated(
        self, runner: CliRunner, tmp_opencase_dir: Path
    ) -> None:
        result = runner.invoke(app, ["mfa", "disable", "--totp-code", "123456"])
        assert result.exit_code == 1
