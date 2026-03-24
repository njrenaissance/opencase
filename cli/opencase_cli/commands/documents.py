"""Document management subcommands."""

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

app = typer.Typer(help="Document management.", no_args_is_help=True)

_DOCUMENT_COLUMNS = [
    "id",
    "filename",
    "content_type",
    "source",
    "classification",
    "matter_id",
]


@app.command("list")
def list_documents(
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """List all documents."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_list(
            client.list_documents(),
            columns=_DOCUMENT_COLUMNS,
            json_mode=json_output,
        )


@app.command("get")
def get_document(
    document_id: Annotated[str, typer.Argument(help="Document UUID.")],
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Get a document by ID."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        print_model(client.get_document(document_id), json_mode=json_output)


@app.command("upload")
def upload_document(
    matter_id: Annotated[str, typer.Option("--matter-id", help="Matter UUID.")],
    filename: Annotated[str, typer.Option("--filename", help="Original filename.")],
    content_type: Annotated[str, typer.Option("--content-type", help="MIME type.")],
    size_bytes: Annotated[
        int, typer.Option("--size-bytes", help="File size in bytes.")
    ],
    file_hash: Annotated[str, typer.Option("--file-hash", help="SHA-256 hex digest.")],
    source: Annotated[
        str, typer.Option("--source", help="Document source.")
    ] = "defense",
    classification: Annotated[
        str, typer.Option("--classification", help="Document classification.")
    ] = "unclassified",
    bates_number: Annotated[
        str | None, typer.Option("--bates-number", help="Bates number.")
    ] = None,
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Upload a document (stub)."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        doc = client.upload_document(
            matter_id=matter_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            file_hash=file_hash,
            source=source,
            classification=classification,
            bates_number=bates_number,
        )
        if json_output:
            print_model(doc, json_mode=True)
        else:
            print_success(f"Document '{doc.filename}' uploaded.")
