"""Document management subcommands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from opencase.exceptions import OpenCaseError
from opencase.hashing import hash_file
from shared.models.enums import Classification, DocumentSource

from opencase_cli.common import BaseUrlOption, JsonOption, TimeoutOption, get_client
from opencase_cli.output import (
    console,
    handle_errors,
    print_error,
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

SUPPORTED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".doc",
        ".docx",
        ".xlsx",
        ".pptx",
        ".rtf",
        ".txt",
        ".md",
        ".csv",
        ".html",
        ".htm",
        ".jpg",
        ".jpeg",
        ".png",
        ".tiff",
        ".tif",
        ".gif",
        ".bmp",
        ".webp",
    }
)


def _discover_files(directory: Path, *, recursive: bool) -> list[Path]:
    """Find files with supported extensions in a directory."""
    pattern = "**/*" if recursive else "*"
    return sorted(
        p
        for p in directory.glob(pattern)
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


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
    file_path: Annotated[
        Path,
        typer.Argument(help="Path to file to upload.", exists=True, dir_okay=False),
    ],
    matter_id: Annotated[str, typer.Option("--matter-id", help="Matter UUID.")],
    source: Annotated[
        str, typer.Option("--source", help="Document source.")
    ] = DocumentSource.defense,
    classification: Annotated[
        str, typer.Option("--classification", help="Document classification.")
    ] = Classification.unclassified,
    bates_number: Annotated[
        str | None, typer.Option("--bates-number", help="Bates number.")
    ] = None,
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Upload a single document to a matter."""
    client = get_client(base_url, timeout, authenticated=True)
    with handle_errors(), client:
        doc = client.upload_document(
            file_path=file_path,
            matter_id=matter_id,
            source=source,
            classification=classification,
            bates_number=bates_number,
        )
        if json_output:
            print_model(doc, json_mode=True)
        else:
            print_success(f"Document '{doc.filename}' uploaded.")


@app.command("bulk-ingest")
def bulk_ingest(
    directory: Annotated[
        Path,
        typer.Argument(
            help="Directory to ingest files from.",
            exists=True,
            file_okay=False,
        ),
    ],
    matter_id: Annotated[str, typer.Option("--matter-id", help="Matter UUID.")],
    source: Annotated[
        str, typer.Option("--source", help="Document source.")
    ] = DocumentSource.defense,
    classification: Annotated[
        str, typer.Option("--classification", help="Document classification.")
    ] = Classification.unclassified,
    recursive: Annotated[
        bool, typer.Option("--recursive/--no-recursive", help="Walk subdirectories.")
    ] = True,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="List files without uploading.")
    ] = False,
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Bulk-ingest documents from a local directory."""
    files = _discover_files(directory, recursive=recursive)

    if not files:
        if json_output:
            console.print("[]", highlight=False)
        else:
            console.print("[dim]No supported files found.[/dim]")
        return

    if dry_run:
        if json_output:
            rows = [{"file": str(f), "status": "pending"} for f in files]
            console.print(json.dumps(rows, indent=2), highlight=False)
        else:
            for f in files:
                console.print(str(f))
            console.print(f"\n[bold]{len(files)}[/bold] file(s) found.")
        return

    client = get_client(base_url, timeout, authenticated=True)
    uploaded = 0
    skipped = 0
    failed = 0
    results: list[dict[str, str]] = []

    with handle_errors(), client:
        for path in files:
            try:
                # Pre-hash locally and check for duplicates before uploading
                file_hash = hash_file(path)
                dup = client.check_duplicate(matter_id=matter_id, file_hash=file_hash)
                if dup.exists:
                    skipped += 1
                    detail = f"duplicate of {dup.document_id}"
                    if json_output:
                        results.append(
                            {"file": str(path), "status": "skipped", "detail": detail}
                        )
                    else:
                        console.print(
                            f"  [yellow]SKIP[/yellow]  {path.name} ({detail})"
                        )
                    continue

                doc = client.upload_document(
                    file_path=path,
                    matter_id=matter_id,
                    source=source,
                    classification=classification,
                )
                uploaded += 1
                if json_output:
                    results.append(
                        {"file": str(path), "status": "uploaded", "detail": str(doc.id)}
                    )
                else:
                    console.print(f"  [green]OK[/green]    {path.name}")
            except OpenCaseError as exc:
                if exc.status_code == 409:  # noqa: PLR2004
                    # Server-side dedup caught a race between check and upload
                    skipped += 1
                    detail = "duplicate (confirmed by server)"
                    if json_output:
                        results.append(
                            {"file": str(path), "status": "skipped", "detail": detail}
                        )
                    else:
                        console.print(
                            f"  [yellow]SKIP[/yellow]  {path.name} ({detail})"
                        )
                else:
                    failed += 1
                    if json_output:
                        results.append(
                            {"file": str(path), "status": "failed", "detail": str(exc)}
                        )
                    else:
                        print_error(f"  FAIL  {path.name}: {exc}")

    total = uploaded + skipped + failed
    if json_output:
        console.print(json.dumps(results, indent=2), highlight=False, soft_wrap=True)
    else:
        console.print(
            f"\n[bold]{uploaded}[/bold] uploaded, "
            f"[bold]{skipped}[/bold] skipped (duplicate), "
            f"[bold]{failed}[/bold] failed "
            f"out of [bold]{total}[/bold] total."
        )

    if failed > 0:
        raise SystemExit(1)
