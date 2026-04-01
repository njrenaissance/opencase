#!/usr/bin/env python3
"""Reset all application data — PostgreSQL, MinIO, and Qdrant.

Truncates all user-data tables (preserving schema and the admin bootstrap),
empties the MinIO bucket, and deletes the Qdrant collection so the next
FastAPI startup recreates it.

Usage (from repo root):
    uv run python scripts/reset_data.py
    uv run python scripts/reset_data.py --env .env
    uv run python scripts/reset_data.py --skip-db --skip-s3   # Qdrant only
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure UTF-8 output on Windows (avoids cp1252 encoding errors).
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

import dotenv
import httpx
import psycopg2
from minio import Minio
from minio.deleteobjects import DeleteObject

# ---------------------------------------------------------------------------
# Defaults (overridden by .env when loaded)
# ---------------------------------------------------------------------------
LOCALHOST_DB_DSN = (
    "postgresql://opencase:FynbWI4dix30YGjioiY8kwg4962U3pwOMMpdUpipW6c="
    "@localhost:5432/opencase"
)
LOCALHOST_TASKS_DSN = (
    "postgresql://opencase:FynbWI4dix30YGjioiY8kwg4962U3pwOMMpdUpipW6c="
    "@localhost:5432/opencase_tasks"
)

# Tables truncated in FK-safe order (CASCADE handles the rest).
# We truncate *all* user-data tables but leave alembic_version intact.
TRUNCATE_TABLES = [
    "documents",
    "matter_access",
    "prompts",
    "refresh_tokens",
    "task_submissions",
    "matters",
    "users",
    "firms",
]


def _reset_postgres(dsn: str, label: str, tables: list[str]) -> None:
    """Truncate tables in a single database."""
    print(f"\n--- PostgreSQL ({label}) ---")
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()
        for table in tables:
            cur.execute(f"TRUNCATE TABLE {table} CASCADE;")  # noqa: S608
            print(f"  truncated: {table}")
        cur.close()
        conn.close()
        print(f"  ✓ {label} reset complete")
    except psycopg2.OperationalError as exc:
        print(f"  ✗ could not connect to {label}: {exc}")
        raise SystemExit(1) from exc


def _reset_minio(
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    use_ssl: bool,
) -> None:
    """Remove all objects from the MinIO bucket (bucket itself is kept)."""
    print("\n--- MinIO (S3) ---")
    client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=use_ssl)
    if not client.bucket_exists(bucket):
        print(f"  bucket '{bucket}' does not exist — nothing to clear")
        return
    objects = client.list_objects(bucket, recursive=True)
    delete_list = [DeleteObject(obj.object_name) for obj in objects]
    if not delete_list:
        print("  bucket is already empty")
        return
    errors = list(client.remove_objects(bucket, delete_list))
    if errors:
        for err in errors:
            print(f"  ✗ failed to delete: {err}")
        raise SystemExit(1)
    print(f"  ✓ removed {len(delete_list)} objects from '{bucket}'")


def _reset_qdrant(host: str, port: int, collection: str) -> None:
    """Delete the Qdrant collection (FastAPI startup will recreate it)."""
    print("\n--- Qdrant ---")
    url = f"http://{host}:{port}/collections/{collection}"
    try:
        resp = httpx.delete(url, timeout=10)
        if resp.status_code == 200:
            print(f"  ✓ deleted collection '{collection}'")
        elif resp.status_code == 404:
            print(f"  collection '{collection}' does not exist — nothing to clear")
        else:
            print(f"  ✗ unexpected response: {resp.status_code} {resp.text}")
            raise SystemExit(1)
    except httpx.ConnectError as exc:
        print(f"  ✗ could not connect to Qdrant: {exc}")
        raise SystemExit(1) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset all OpenCase data stores")
    parser.add_argument("--env", default=".env", help="Path to .env file (default: .env)")
    parser.add_argument("--skip-db", action="store_true", help="Skip PostgreSQL reset")
    parser.add_argument("--skip-s3", action="store_true", help="Skip MinIO reset")
    parser.add_argument("--skip-qdrant", action="store_true", help="Skip Qdrant reset")
    args = parser.parse_args()

    dotenv.load_dotenv(args.env, override=True)

    print("=== OpenCase Data Reset ===")

    if not args.skip_db:
        # Build localhost DSNs from env (replace Docker hostnames with localhost)
        pg_user = os.getenv("POSTGRES_USER", "opencase")
        pg_pass = os.getenv("POSTGRES_PASSWORD", "")
        pg_port = os.getenv("POSTGRES_PORT", "5432")

        main_dsn = f"postgresql://{pg_user}:{pg_pass}@localhost:{pg_port}/opencase"
        tasks_dsn = f"postgresql://{pg_user}:{pg_pass}@localhost:{pg_port}/opencase_tasks"

        _reset_postgres(main_dsn, "opencase", TRUNCATE_TABLES)
        _reset_postgres(tasks_dsn, "opencase_tasks", ["celery_taskmeta", "celery_tasksetmeta"])

    if not args.skip_s3:
        _reset_minio(
            endpoint=os.getenv("OPENCASE_S3_ENDPOINT", "minio:9000").replace("minio", "localhost"),
            access_key=os.getenv("OPENCASE_S3_ACCESS_KEY", "opencase"),
            secret_key=os.getenv("OPENCASE_S3_SECRET_KEY", "changeme"),
            bucket=os.getenv("OPENCASE_S3_BUCKET", "opencase"),
            use_ssl=os.getenv("OPENCASE_S3_USE_SSL", "false").lower() == "true",
        )

    if not args.skip_qdrant:
        qdrant_host = os.getenv("OPENCASE_QDRANT_HOST", "qdrant").replace("qdrant", "localhost")
        qdrant_port = int(os.getenv("OPENCASE_QDRANT_PORT", "6333"))
        collection = os.getenv("OPENCASE_QDRANT_COLLECTION", "opencase")
        _reset_qdrant(qdrant_host, qdrant_port, collection)

    print("\n=== Reset complete ===")
    print("Restart the stack to re-bootstrap admin and global knowledge matter:")
    print("  docker compose -f infrastructure/docker-compose.yml --env-file .env restart fastapi")


if __name__ == "__main__":
    main()
