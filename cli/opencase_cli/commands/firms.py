"""Firm subcommands."""

from __future__ import annotations

import typer

from opencase_cli.common import BaseUrlOption, JsonOption, TimeoutOption, get_client
from opencase_cli.output import handle_errors, print_model

app = typer.Typer(help="Firm information.", no_args_is_help=True)


@app.command("get")
def get_firm(
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Show current firm details."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_model(client.get_firm(), json_mode=json_output)
