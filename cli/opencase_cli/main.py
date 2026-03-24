"""OpenCase CLI entry point — Typer application and top-level commands."""

from __future__ import annotations

from typing import Annotated

import opencase
import typer
from rich.table import Table

import opencase_cli
from opencase_cli.commands import (
    auth,
    documents,
    firms,
    health,
    matters,
    mfa,
    prompts,
    users,
)
from opencase_cli.config import CLIConfig, config_path, load_config, save_config
from opencase_cli.output import console, print_json, print_success

app = typer.Typer(
    name="opencase",
    help="OpenCase CLI — criminal defense discovery platform.",
    no_args_is_help=True,
)

# -- register command modules ------------------------------------------------

app.command()(health.health)
app.command()(health.ready)
app.command()(auth.login)
app.command()(auth.logout)
app.command()(auth.whoami)
app.add_typer(mfa.app, name="mfa")
app.add_typer(users.app, name="user")
app.add_typer(matters.app, name="matter")
app.add_typer(documents.app, name="document")
app.add_typer(prompts.app, name="prompt")
app.add_typer(firms.app, name="firm")


# -- top-level commands ------------------------------------------------------


@app.command()
def configure(
    base_url: Annotated[
        str | None,
        typer.Option("--base-url", help="API base URL."),
    ] = None,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Request timeout in seconds."),
    ] = None,
) -> None:
    """Configure CLI connection settings (interactive)."""
    current = load_config()

    if base_url is None:
        base_url = typer.prompt("Base URL", default=current.base_url)
    if timeout is None:
        timeout = float(typer.prompt("Timeout (seconds)", default=current.timeout))

    config = CLIConfig(base_url=base_url, timeout=timeout)
    save_config(config)
    print_success(f"Configuration saved to {config_path()}")


@app.command()
def version(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON."),
    ] = False,
) -> None:
    """Print CLI and SDK versions."""
    if json_output:
        print_json(
            {
                "cli_version": opencase_cli.__version__,
                "sdk_version": opencase.__version__,
            }
        )
    else:
        table = Table(show_header=False, show_edge=False, pad_edge=False)
        table.add_column("Component", style="bold")
        table.add_column("Version")
        table.add_row("CLI", opencase_cli.__version__)
        table.add_row("SDK", opencase.__version__)
        console.print(table)
