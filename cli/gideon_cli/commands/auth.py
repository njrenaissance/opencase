"""Authentication commands — login, logout, whoami."""

from __future__ import annotations

from typing import Annotated

import typer
from shared.models.auth import MfaRequiredResponse

from gideon_cli.common import BaseUrlOption, JsonOption, TimeoutOption, get_client
from gideon_cli.output import handle_errors, print_json, print_model, print_success
from gideon_cli.tokens import clear_tokens, save_tokens


def login(
    email: Annotated[
        str | None,
        typer.Option("--email", "-e", help="Account email address."),
    ] = None,
    password: Annotated[
        str | None,
        typer.Option(
            "--password",
            "-p",
            help="Account password (prefer interactive prompt to avoid shell history).",
            hide_input=True,
        ),
    ] = None,
    totp_code: Annotated[
        str | None,
        typer.Option("--totp-code", help="TOTP code (skip interactive MFA prompt)."),
    ] = None,
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Authenticate with email and password."""
    if email is None:
        email = typer.prompt("Email")
    if password is None:
        password = typer.prompt("Password", hide_input=True)

    client = get_client(base_url, timeout)
    with handle_errors(), client:
        result = client.login(email=email, password=password)

        if isinstance(result, MfaRequiredResponse):
            if totp_code is None:
                totp_code = typer.prompt("TOTP code")
            result = client.verify_mfa(mfa_token=result.mfa_token, totp_code=totp_code)

        save_tokens(result.access_token, result.refresh_token)

        if json_output:
            print_json({"authenticated": True})
        else:
            print_success("Logged in successfully.")


def logout(
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Log out and clear stored tokens."""
    client = get_client(base_url, timeout, authenticated=True)
    try:
        with handle_errors(), client:
            client.logout()
    finally:
        clear_tokens()
    if json_output:
        print_json({"logged_out": True})
    else:
        print_success("Logged out.")


def whoami(
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Show current authenticated user."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_model(client.get_current_user(), json_mode=json_output)
