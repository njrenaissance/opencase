"""Output formatting — Rich tables, JSON mode, error display."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import httpx
from gideon import (
    AuthenticationError,
    AuthorizationError,
    GideonError,
)
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


def print_model(model: BaseModel, *, json_mode: bool) -> None:
    """Print a Pydantic model as JSON or a Rich key-value table."""
    if json_mode:
        console.print(model.model_dump_json(indent=2), highlight=False)
        return

    data = model.model_dump()
    table = Table(show_header=False, show_edge=False, pad_edge=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for key, value in data.items():
        if isinstance(value, dict):
            for sub_key, sub_val in value.items():
                table.add_row(f"  {sub_key}", str(sub_val))
        else:
            table.add_row(key, str(value))
    console.print(table)


def print_list(
    models: Sequence[BaseModel],
    *,
    columns: list[str],
    json_mode: bool,
) -> None:
    """Print a list of Pydantic models as JSON array or Rich table."""
    if json_mode:
        rows = [m.model_dump(mode="json") for m in models]
        console.print(json.dumps(rows, indent=2, default=str), highlight=False)
        return

    if not models:
        console.print("[dim]No results.[/dim]")
        return

    table = Table(show_edge=False, pad_edge=False)
    for col in columns:
        table.add_column(col, style="bold" if col == columns[0] else "")
    for model in models:
        data = model.model_dump()
        table.add_row(*(str(data.get(c, "")) for c in columns))
    console.print(table)


def print_json(data: object) -> None:
    """Print arbitrary data as formatted JSON."""
    console.print(json.dumps(data, indent=2, default=str), highlight=False)


def print_success(message: str) -> None:
    """Print a green success message."""
    console.print(f"[green]{message}[/green]")


def print_error(message: str) -> None:
    """Print a red error message to stderr."""
    err_console.print(f"[red]{message}[/red]")


@contextmanager
def handle_errors() -> Iterator[None]:
    """Catch SDK and connection errors, print them, and exit."""
    try:
        yield
    except AuthenticationError as exc:
        print_error(f"Authentication failed: {exc}")
        raise SystemExit(1) from None
    except AuthorizationError as exc:
        print_error(f"Access denied: {exc}")
        raise SystemExit(1) from None
    except GideonError as exc:
        print_error(f"API error: {exc}")
        raise SystemExit(1) from None
    except httpx.ConnectError:
        print_error("Cannot connect to Gideon server. Is it running?")
        raise SystemExit(1) from None
    except httpx.TimeoutException:
        print_error("Request timed out. Try increasing --timeout.")
        raise SystemExit(1) from None
