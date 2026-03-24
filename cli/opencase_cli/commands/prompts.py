"""Prompt management subcommands."""

from __future__ import annotations

from typing import Annotated

import typer

from opencase_cli.common import BaseUrlOption, JsonOption, TimeoutOption, get_client
from opencase_cli.output import (
    handle_errors,
    print_list,
    print_model,
    print_success,
)

app = typer.Typer(help="AI prompt management.", no_args_is_help=True)

_PROMPT_COLUMNS = ["id", "matter_id", "query", "created_at"]


@app.command("list")
def list_prompts(
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """List all prompts."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_list(
            client.list_prompts(),
            columns=_PROMPT_COLUMNS,
            json_mode=json_output,
        )


@app.command("get")
def get_prompt(
    prompt_id: Annotated[str, typer.Argument(help="Prompt UUID.")],
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Get a prompt by ID."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_model(client.get_prompt(prompt_id), json_mode=json_output)


@app.command("submit")
def submit_prompt(
    matter_id: Annotated[str, typer.Option("--matter-id", help="Matter UUID.")],
    query: Annotated[str, typer.Argument(help="Query text.")],
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Submit a prompt to the AI chatbot (stub)."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        prompt = client.submit_prompt(matter_id=matter_id, query=query)
        if json_output:
            print_model(prompt, json_mode=True)
        else:
            print_success(f"Prompt submitted. Response: {prompt.response}")
