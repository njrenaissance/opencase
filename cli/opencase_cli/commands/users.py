"""User management subcommands."""

from __future__ import annotations

from typing import Annotated

import typer

from opencase_cli.common import BaseUrlOption, JsonOption, TimeoutOption, get_client
from opencase_cli.output import (
    handle_errors,
    print_error,
    print_list,
    print_model,
    print_success,
)

app = typer.Typer(help="User management.", no_args_is_help=True)

_USER_COLUMNS = ["id", "email", "first_name", "last_name", "role", "is_active"]


@app.command("list")
def list_users(
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """List all users in the firm."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_list(client.list_users(), columns=_USER_COLUMNS, json_mode=json_output)


@app.command("get")
def get_user(
    user_id: Annotated[str, typer.Argument(help="User UUID.")],
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Get a user by ID."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_model(client.get_user(user_id), json_mode=json_output)


@app.command("create")
def create_user(
    email: Annotated[str, typer.Option("--email", help="Email address.")],
    password: Annotated[
        str,
        typer.Option("--password", help="Password.", hide_input=True),
    ],
    first_name: Annotated[str, typer.Option("--first-name", help="First name.")],
    last_name: Annotated[str, typer.Option("--last-name", help="Last name.")],
    role: Annotated[
        str,
        typer.Option("--role", help="Role: admin|attorney|paralegal|investigator."),
    ],
    title: Annotated[str | None, typer.Option("--title", help="Title.")] = None,
    middle_initial: Annotated[
        str | None, typer.Option("--middle-initial", help="Middle initial.")
    ] = None,
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Create a new user."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        user = client.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            title=title,
            middle_initial=middle_initial,
        )
        if json_output:
            print_model(user, json_mode=True)
        else:
            print_success(f"User {user.email} created.")


@app.command("update")
def update_user(
    user_id: Annotated[str, typer.Argument(help="User UUID.")],
    email: Annotated[str | None, typer.Option("--email")] = None,
    first_name: Annotated[str | None, typer.Option("--first-name")] = None,
    last_name: Annotated[str | None, typer.Option("--last-name")] = None,
    role: Annotated[str | None, typer.Option("--role")] = None,
    title: Annotated[str | None, typer.Option("--title")] = None,
    middle_initial: Annotated[str | None, typer.Option("--middle-initial")] = None,
    is_active: Annotated[bool | None, typer.Option("--is-active")] = None,
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Update a user (only provided fields are changed)."""
    fields: dict[str, object] = {}
    if email is not None:
        fields["email"] = email
    if first_name is not None:
        fields["first_name"] = first_name
    if last_name is not None:
        fields["last_name"] = last_name
    if role is not None:
        fields["role"] = role
    if title is not None:
        fields["title"] = title
    if middle_initial is not None:
        fields["middle_initial"] = middle_initial
    if is_active is not None:
        fields["is_active"] = is_active

    if not fields:
        print_error("No fields to update. Provide at least one option.")
        raise SystemExit(1)

    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        user = client.update_user(user_id, **fields)
        if json_output:
            print_model(user, json_mode=True)
        else:
            print_success(f"User {user.email} updated.")
