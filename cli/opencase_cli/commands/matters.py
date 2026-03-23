"""Matter management subcommands."""

from __future__ import annotations

from typing import Annotated

import typer

from opencase_cli.common import BaseUrlOption, JsonOption, TimeoutOption, get_client
from opencase_cli.output import (
    handle_errors,
    print_error,
    print_json,
    print_list,
    print_model,
    print_success,
)

app = typer.Typer(help="Matter management.", no_args_is_help=True)

_MATTER_COLUMNS = ["id", "name", "status", "legal_hold", "client_id"]
_ACCESS_COLUMNS = [
    "user_id",
    "matter_id",
    "view_work_product",
    "assigned_at",
]


@app.command("list")
def list_matters(
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """List all matters."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_list(
            client.list_matters(),
            columns=_MATTER_COLUMNS,
            json_mode=json_output,
        )


@app.command("get")
def get_matter(
    matter_id: Annotated[str, typer.Argument(help="Matter UUID.")],
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Get a matter by ID."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_model(client.get_matter(matter_id), json_mode=json_output)


@app.command("create")
def create_matter(
    name: Annotated[str, typer.Option("--name", help="Matter name.")],
    client_id: Annotated[str, typer.Option("--client-id", help="Client UUID.")],
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Create a new matter."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        matter = client.create_matter(name=name, client_id=client_id)
        if json_output:
            print_model(matter, json_mode=True)
        else:
            print_success(f"Matter '{matter.name}' created.")


@app.command("update")
def update_matter(
    matter_id: Annotated[str, typer.Argument(help="Matter UUID.")],
    name: Annotated[str | None, typer.Option("--name")] = None,
    status: Annotated[str | None, typer.Option("--status")] = None,
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Update a matter (only provided fields are changed)."""
    fields: dict[str, object] = {}
    if name is not None:
        fields["name"] = name
    if status is not None:
        fields["status"] = status

    if not fields:
        print_error("No fields to update. Provide at least one option.")
        raise SystemExit(1)

    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        matter = client.update_matter(matter_id, **fields)
        if json_output:
            print_model(matter, json_mode=True)
        else:
            print_success(f"Matter '{matter.name}' updated.")


# -- access subcommands ------------------------------------------------------


@app.command("access-list")
def list_access(
    matter_id: Annotated[str, typer.Argument(help="Matter UUID.")],
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """List users with access to a matter."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_list(
            client.list_matter_access(matter_id),
            columns=_ACCESS_COLUMNS,
            json_mode=json_output,
        )


@app.command("access-grant")
def grant_access(
    matter_id: Annotated[str, typer.Argument(help="Matter UUID.")],
    user_id: Annotated[str, typer.Option("--user-id", help="User UUID.")],
    view_work_product: Annotated[
        bool,
        typer.Option("--view-work-product", help="Grant work product access."),
    ] = False,
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Grant a user access to a matter."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        result = client.grant_matter_access(
            matter_id,
            user_id=user_id,
            view_work_product=view_work_product,
        )
        if json_output:
            print_model(result, json_mode=True)
        else:
            print_success("Access granted.")


@app.command("access-revoke")
def revoke_access(
    matter_id: Annotated[str, typer.Argument(help="Matter UUID.")],
    user_id: Annotated[str, typer.Option("--user-id", help="User UUID to revoke.")],
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Revoke a user's access to a matter."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        result = client.revoke_matter_access(matter_id, user_id)
        if json_output:
            print_json({"detail": result.detail})
        else:
            print_success(result.detail)
