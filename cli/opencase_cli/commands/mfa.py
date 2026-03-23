"""MFA management subcommands — setup, confirm, disable."""

from __future__ import annotations

from typing import Annotated

import typer

from opencase_cli.common import BaseUrlOption, JsonOption, TimeoutOption, get_client
from opencase_cli.output import handle_errors, print_model, print_success

app = typer.Typer(help="Manage multi-factor authentication.", no_args_is_help=True)


@app.command()
def setup(
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Begin MFA setup — shows TOTP secret and provisioning URI."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_model(client.mfa_setup(), json_mode=json_output)


@app.command()
def confirm(
    totp_code: Annotated[
        str | None,
        typer.Option("--totp-code", help="TOTP code to confirm setup."),
    ] = None,
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Confirm MFA setup with a TOTP code."""
    if totp_code is None:
        totp_code = typer.prompt("TOTP code")

    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        resp = client.mfa_confirm(totp_code=totp_code)
        if json_output:
            print_model(resp, json_mode=True)
        else:
            msg = "MFA enabled." if resp.enabled else "MFA confirmation failed."
            print_success(msg)


@app.command()
def disable(
    totp_code: Annotated[
        str | None,
        typer.Option("--totp-code", help="TOTP code to disable MFA."),
    ] = None,
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Disable MFA with a TOTP code."""
    if totp_code is None:
        totp_code = typer.prompt("TOTP code")

    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        resp = client.mfa_disable(totp_code=totp_code)
        if json_output:
            print_model(resp, json_mode=True)
        else:
            print_success(
                "MFA disabled." if not resp.enabled else "MFA disable failed."
            )
