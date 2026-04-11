"""Task management subcommands."""

from __future__ import annotations

from typing import Annotated

import typer
from shared.models.enums import TaskState

from gideon_cli.common import BaseUrlOption, JsonOption, TimeoutOption, get_client
from gideon_cli.output import (
    handle_errors,
    print_list,
    print_model,
    print_success,
)

app = typer.Typer(help="Background task management.", no_args_is_help=True)

_TASK_COLUMNS = ["id", "task_name", "status", "submitted_at"]


@app.command("list")
def list_tasks(
    status: Annotated[
        TaskState | None,
        typer.Option("--status", help="Filter by task state."),
    ] = None,
    task_name: Annotated[
        str | None,
        typer.Option("--task-name", help="Filter by task name."),
    ] = None,
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """List background tasks."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_list(
            client.list_tasks(status=status, task_name=task_name),
            columns=_TASK_COLUMNS,
            json_mode=json_output,
        )


@app.command("get")
def get_task(
    task_id: Annotated[str, typer.Argument(help="Task ID.")],
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Get task details by ID."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_model(client.get_task(task_id), json_mode=json_output)


@app.command("submit")
def submit_task(
    task_name: Annotated[
        str, typer.Option("--task-name", help="Registered task name.")
    ],
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Submit a background task."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        result = client.submit_task(task_name=task_name)
        if json_output:
            print_model(result, json_mode=True)
        else:
            print_success(f"Task submitted: {result.task_id}")


@app.command("cancel")
def cancel_task(
    task_id: Annotated[str, typer.Argument(help="Task ID to cancel.")],
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Cancel a pending or running task."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        result = client.cancel_task(task_id)
        if json_output:
            print_model(result, json_mode=True)
        else:
            print_success(result.detail)
