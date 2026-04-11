"""Submit chunk_document tasks for existing documents.

Reads extracted text from S3 (extracted.json) and submits chunking tasks
via the API for each document that has been extracted.

Usage:
    uv run python scripts/chunk_documents.py          # chunk all documents
    uv run python scripts/chunk_documents.py --limit 3  # chunk first 3
"""

from __future__ import annotations

import argparse
import json
import time

POLL_TIMEOUT_SECONDS = 300

import dotenv
from minio import Minio
from gideon import Client


BASE_URL = "http://127.0.0.1:8000"


def get_extracted_text(
    minio_client: Minio, bucket: str, firm_id: str, matter_id: str, doc_id: str
) -> str | None:
    """Fetch extracted.json from S3 and return the text field."""
    key = f"{firm_id}/{matter_id}/{doc_id}/extracted.json"
    try:
        response = minio_client.get_object(bucket, key)
        data = json.loads(response.read())
        response.close()
        response.release_conn()
        return data.get("text")
    except Exception as exc:
        print(f"  No extracted.json: {exc}")
        return None


def s3_prefix(firm_id: str, matter_id: str, doc_id: str) -> str:
    return f"{firm_id}/{matter_id}/{doc_id}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit chunking tasks")
    parser.add_argument("--limit", type=int, default=0, help="Max documents to chunk (0 = all)")
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    args = parser.parse_args()

    s3_access_key = dotenv.get_key(args.env_file, "GIDEON_S3_ACCESS_KEY")
    s3_secret_key = dotenv.get_key(args.env_file, "GIDEON_S3_SECRET_KEY")
    s3_bucket = dotenv.get_key(args.env_file, "GIDEON_S3_BUCKET") or "gideon"
    admin_email = dotenv.get_key(args.env_file, "GIDEON_ADMIN_EMAIL")
    admin_password = dotenv.get_key(args.env_file, "GIDEON_ADMIN_PASSWORD")

    if not s3_access_key:
        raise SystemExit("GIDEON_S3_ACCESS_KEY is required")
    if not s3_secret_key:
        raise SystemExit("GIDEON_S3_SECRET_KEY is required")
    if not admin_email or not admin_password:
        raise SystemExit("GIDEON_ADMIN_EMAIL and GIDEON_ADMIN_PASSWORD are required")

    minio_client = Minio(
        "localhost:9000",
        access_key=s3_access_key,
        secret_key=s3_secret_key,
        secure=False,
    )

    with Client(base_url=BASE_URL) as client:
        client.login(email=admin_email, password=admin_password)

        docs = client.list_documents()
        if args.limit > 0:
            docs = docs[: args.limit]

        print(f"Found {len(docs)} document(s) to chunk\n")

        task_ids = []
        for doc in docs:
            detail = client.get_document(str(doc.id))
            print(f"[{doc.filename}] id={doc.id}")

            text = get_extracted_text(
                minio_client, s3_bucket, str(detail.firm_id), str(doc.matter_id), str(doc.id)
            )
            if text is None:
                print("  Skipped — no extracted text\n")
                continue

            print(f"  Extracted text: {len(text)} chars")

            prefix = s3_prefix(str(detail.firm_id), str(doc.matter_id), str(doc.id))
            metadata = {
                "firm_id": str(detail.firm_id),
                "matter_id": str(doc.matter_id),
                "document_id": str(doc.id),
                "filename": doc.filename,
                "source": doc.source.value if hasattr(doc.source, "value") else str(doc.source),
                "classification": (
                    doc.classification.value
                    if hasattr(doc.classification, "value")
                    else str(doc.classification)
                ),
            }

            result = client.submit_task(
                task_name="chunk_document",
                kwargs={
                    "document_id": str(doc.id),
                    "text": text,
                    "metadata": metadata,
                    "s3_prefix": prefix,
                },
            )
            print(f"  Task submitted: {result.task_id}\n")
            task_ids.append((doc.filename, result.task_id))

        if not task_ids:
            print("No tasks submitted.")
            client.logout()
            return

        # Poll for completion
        print(f"\nWaiting for {len(task_ids)} task(s)...\n")
        for filename, task_id in task_ids:
            deadline = time.time() + POLL_TIMEOUT_SECONDS
            while time.time() < deadline:
                task = client.get_task(task_id)
                if task.status in ("completed", "SUCCESS"):
                    chunk_count = (
                        task.result.get("chunk_count", "?") if isinstance(task.result, dict) else "?"
                    )
                    print(f"  [{filename}] Done — {chunk_count} chunks")
                    break
                elif task.status in ("failed", "FAILURE"):
                    print(f"  [{filename}] FAILED")
                    break
                else:
                    time.sleep(2)
            else:
                print(f"  [{filename}] TIMEOUT after {POLL_TIMEOUT_SECONDS}s")

        client.logout()


if __name__ == "__main__":
    main()
