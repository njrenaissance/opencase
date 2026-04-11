"""Tests for login, logout, and whoami commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from gideon import AuthenticationError
from typer.testing import CliRunner

from gideon_cli.main import app
from gideon_cli.tokens import load_tokens

from .conftest import (
    LOGOUT_RESPONSE,
    MFA_REQUIRED,
    TOKEN_RESPONSE,
    USER_RESPONSE,
)

_PATCH_GET_CLIENT = "gideon_cli.commands.auth.get_client"


class TestLogin:
    def test_login_success(
        self, runner: CliRunner, mock_client: Any, tmp_gideon_dir: Path
    ) -> None:
        mock_client.login.return_value = TOKEN_RESPONSE
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app, ["login", "--email", "u@f.com", "--password", "secret"]
            )
        assert result.exit_code == 0
        assert "Logged in" in result.output
        assert load_tokens() is not None

    def test_login_json(
        self, runner: CliRunner, mock_client: Any, tmp_gideon_dir: Path
    ) -> None:
        mock_client.login.return_value = TOKEN_RESPONSE
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app, ["login", "--email", "u@f.com", "--password", "s", "--json"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["authenticated"] is True

    def test_login_mfa_flow(
        self, runner: CliRunner, mock_client: Any, tmp_gideon_dir: Path
    ) -> None:
        mock_client.login.return_value = MFA_REQUIRED
        mock_client.verify_mfa.return_value = TOKEN_RESPONSE
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "login",
                    "--email",
                    "u@f.com",
                    "--password",
                    "s",
                    "--totp-code",
                    "123456",
                ],
            )
        assert result.exit_code == 0
        mock_client.verify_mfa.assert_called_once_with(
            mfa_token="mfa-tok", totp_code="123456"
        )

    def test_login_invalid_credentials(
        self, runner: CliRunner, mock_client: Any, tmp_gideon_dir: Path
    ) -> None:
        mock_client.login.side_effect = AuthenticationError(
            "bad creds", status_code=401
        )
        with patch(_PATCH_GET_CLIENT, return_value=mock_client):
            result = runner.invoke(
                app, ["login", "--email", "u@f.com", "--password", "wrong"]
            )
        assert result.exit_code == 1


class TestLogout:
    def test_logout_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.logout.return_value = LOGOUT_RESPONSE
        with patch("gideon_cli.commands.auth.get_client", return_value=mock_client):
            result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0
        assert "Logged out" in result.output
        assert load_tokens() is None

    def test_logout_not_logged_in(
        self, runner: CliRunner, tmp_gideon_dir: Path
    ) -> None:
        result = runner.invoke(app, ["logout"])
        assert result.exit_code == 1


class TestWhoami:
    def test_whoami_success(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.get_current_user.return_value = USER_RESPONSE
        with patch("gideon_cli.commands.auth.get_client", return_value=mock_client):
            result = runner.invoke(app, ["whoami"])
        assert result.exit_code == 0
        assert "user@firm.com" in result.output

    def test_whoami_json(
        self,
        runner: CliRunner,
        mock_client: Any,
        tmp_gideon_dir: Path,
        stored_tokens: tuple[str, str],
    ) -> None:
        mock_client.get_current_user.return_value = USER_RESPONSE
        with patch("gideon_cli.commands.auth.get_client", return_value=mock_client):
            result = runner.invoke(app, ["whoami", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["email"] == "user@firm.com"
        assert data["role"] == "attorney"

    def test_whoami_not_logged_in(
        self, runner: CliRunner, tmp_gideon_dir: Path
    ) -> None:
        result = runner.invoke(app, ["whoami"])
        assert result.exit_code == 1
