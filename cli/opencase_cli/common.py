"""Shared Typer parameter types and client factory."""

from __future__ import annotations

from typing import Annotated

import typer
from opencase import Client

from opencase_cli.config import load_config
from opencase_cli.output import print_error
from opencase_cli.tokens import load_tokens

# Re-usable Annotated types for common CLI options.
BaseUrlOption = Annotated[
    str | None,
    typer.Option("--base-url", envvar="OPENCASE_BASE_URL", help="API base URL."),
]
TimeoutOption = Annotated[
    float | None,
    typer.Option("--timeout", envvar="OPENCASE_TIMEOUT", help="Timeout in seconds."),
]
JsonOption = Annotated[
    bool,
    typer.Option("--json", help="Output as JSON."),
]


def get_client(
    base_url: str | None = None,
    timeout: float | None = None,
    *,
    authenticated: bool = False,
) -> Client:
    """Create a configured ``Client``, optionally with stored tokens."""
    config = load_config(base_url=base_url, timeout=timeout)
    client = Client(base_url=config.base_url, timeout=config.timeout)

    if authenticated:
        tokens = load_tokens()
        if tokens is None:
            print_error("Not logged in. Run 'opencase login' first.")
            raise SystemExit(1)
        client._auth.store_tokens(tokens[0], tokens[1])  # noqa: SLF001

    return client
