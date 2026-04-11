#!/usr/bin/env python3
"""Upload a file via the API and verify the DB record + S3 object.

Uploads a file to the first available matter (or creates one), then
verifies the document exists in the database and MinIO.  Useful for
end-to-end validation of the document ingestion pipeline.

Usage (from repo root):
    uv run python scripts/upload_file.py
    uv run python scripts/upload_file.py --file ./evidence.pdf
    uv run python scripts/upload_file.py --env .env
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
import uuid
from pathlib import Path

import dotenv
import httpx
from minio import Minio
from gideon import Client

BASE_URL = "http://127.0.0.1:8000"
MINIO_ENDPOINT = "localhost:9000"


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def pick_matter(client: Client) -> dict:
    """Return the first matter, or create one if none exist."""
    matters = client.list_matters()
    if matters:
        matter = {"id": str(matters[0].id), "name": matters[0].name}
        print(f"Using matter: {matter['name']} ({matter['id']})")  # noqa: T201
        return matter

    print("No matters found — creating one...")  # noqa: T201
    m = client.create_matter(name="Test Upload Matter", client_id=str(uuid.uuid4()))
    print(f"  Created matter: {m.name} ({m.id})")  # noqa: T201
    return {"id": str(m.id), "name": m.name}


def prepare_file(file_path: Path | None) -> tuple[Path, str, bool]:
    """Resolve or create the file to upload.  Returns (path, sha256, cleanup)."""
    if file_path is not None:
        if not file_path.exists():
            print(f"ERROR: File not found: {file_path}")  # noqa: T201
            sys.exit(1)
        cleanup = False
    else:
        f = tempfile.NamedTemporaryFile(suffix=".txt", prefix="gideon_", delete=False)  # noqa: SIM115
        f.write(f"Gideon upload test — {uuid.uuid4()}\n".encode())
        f.close()
        file_path = Path(f.name)
        cleanup = True
        print(f"Created test file: {file_path}")  # noqa: T201

    local_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    print(f"Local file:     {file_path.name} ({file_path.stat().st_size} bytes)")  # noqa: T201
    print(f"Local SHA-256:  {local_hash}")  # noqa: T201
    return file_path, local_hash, cleanup


def upload(client: Client, file_path: Path, matter_id: str) -> object:
    """Upload the file and print the response."""
    print("\nUploading...")  # noqa: T201
    doc = client.upload_document(file_path=file_path, matter_id=matter_id)
    print(f"  Document ID:  {doc.id}")  # noqa: T201
    print(f"  Filename:     {doc.filename}")  # noqa: T201
    print(f"  Size:         {doc.size_bytes} bytes")  # noqa: T201
    print(f"  Hash:         {doc.file_hash}")  # noqa: T201
    return doc


def verify_hash(doc: object, local_hash: str) -> None:
    """Compare server-computed hash against local hash."""
    if doc.file_hash != local_hash:
        print(f"\nFAIL: Hash mismatch! Server={doc.file_hash} Local={local_hash}")  # noqa: T201
        sys.exit(1)
    print("  Hash match:   OK")  # noqa: T201


def verify_database(client: Client, doc_id: str) -> None:
    """Confirm the document record exists via API."""
    print("\nVerifying database (GET /documents/{id})...")  # noqa: T201
    db_doc = client.get_document(doc_id)
    print(f"  DB record:    OK (firm={db_doc.firm_id})")  # noqa: T201


def verify_s3(
    doc: object,
    minio_endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
) -> None:
    """Confirm the S3 object exists in MinIO and print metadata."""
    print("\nVerifying S3 (MinIO stat_object)...")  # noqa: T201
    mc = Minio(minio_endpoint, access_key=access_key, secret_key=secret_key, secure=False)

    ext = Path(doc.filename).suffix.lstrip(".") or "bin"
    key = f"{doc.firm_id}/{doc.matter_id}/{doc.id}/original.{ext}"

    try:
        stat = mc.stat_object(bucket, key)
    except Exception as exc:
        print(f"FAIL: S3 object not found at {key}: {exc}")  # noqa: T201
        sys.exit(1)

    meta = stat.metadata
    print(f"  S3 key:       {key}")  # noqa: T201
    print(f"  S3 size:      {stat.size} bytes")  # noqa: T201
    print(f"  S3 sha256:    {meta.get('x-amz-meta-sha256', '???')}")  # noqa: T201
    print(f"  S3 timestamp: {meta.get('x-amz-meta-ingestion-timestamp', '???')}")  # noqa: T201


def verify_download(client: Client, doc_id: str, local_hash: str) -> None:
    """Download the file and compare its hash to the original."""
    print("\nVerifying download (GET /documents/{id}/download)...")  # noqa: T201
    resp = httpx.get(
        f"{BASE_URL}/documents/{doc_id}/download",
        headers=client._auth.authorization_header,  # noqa: SLF001
        timeout=30,
    )
    if resp.status_code != 200:  # noqa: PLR2004
        print(f"FAIL: Download returned {resp.status_code}")  # noqa: T201
        sys.exit(1)
    if hashlib.sha256(resp.content).hexdigest() != local_hash:
        print("FAIL: Downloaded content hash mismatch!")  # noqa: T201
        sys.exit(1)
    print(f"  Download:     OK ({len(resp.content)} bytes, hash matches)")  # noqa: T201


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(config_file: str, file_path: Path | None = None) -> None:
    admin_email = dotenv.get_key(config_file, "GIDEON_ADMIN_EMAIL")
    admin_password = dotenv.get_key(config_file, "GIDEON_ADMIN_PASSWORD")
    s3_access = dotenv.get_key(config_file, "GIDEON_S3_ACCESS_KEY") or "gideon"
    s3_secret = dotenv.get_key(config_file, "GIDEON_S3_SECRET_KEY") or "changeme"
    s3_bucket = dotenv.get_key(config_file, "GIDEON_S3_BUCKET") or "gideon"

    if not admin_email or not admin_password:
        print("ERROR: GIDEON_ADMIN_EMAIL / GIDEON_ADMIN_PASSWORD not set")  # noqa: T201
        sys.exit(1)

    with Client(base_url=BASE_URL) as client:
        print(f"Logging in as {admin_email}")  # noqa: T201
        client.login(email=admin_email, password=admin_password)

        matter = pick_matter(client)
        file_path, local_hash, cleanup = prepare_file(file_path)
        doc = upload(client, file_path, matter["id"])
        verify_hash(doc, local_hash)
        verify_database(client, str(doc.id))
        verify_s3(doc, MINIO_ENDPOINT, s3_access, s3_secret, s3_bucket)
        verify_download(client, str(doc.id), local_hash)

        client.logout()

    if cleanup:
        file_path.unlink(missing_ok=True)

    print("\n=== ALL CHECKS PASSED ===")  # noqa: T201


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload a file and verify DB + S3.")
    parser.add_argument("--file", type=Path, help="File to upload (default: auto-generated)")
    parser.add_argument("--env", default=".env", help="Path to .env file (default: .env)")
    args = parser.parse_args()
    main(config_file=args.env, file_path=args.file)
