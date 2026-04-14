#!/usr/bin/env python3
"""Backfill the 'text' payload field on existing Qdrant points.

Documents ingested before Feature 7.3 do not carry chunk text in their
Qdrant payload.  This script scrolls all affected points, fetches the
text from the corresponding chunks.json in MinIO, and patches each
point in place using set_payload.  No re-ingestion required.

Usage:
    python scripts/backfill_chunk_text.py

    # Limit to one firm or matter:
    python scripts/backfill_chunk_text.py --firm-id <uuid>
    python scripts/backfill_chunk_text.py --firm-id <uuid> --matter-id <uuid>

    # Dry-run (shows what would be patched, writes nothing):
    python scripts/backfill_chunk_text.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

import httpx
from minio import Minio  # type: ignore[import-untyped]
from qdrant_client import QdrantClient, models

# ---------------------------------------------------------------------------
# Constants — mirror defaults from app/core/config.py
# ---------------------------------------------------------------------------

QDRANT_URL = "http://localhost:6333"
COLLECTION = "gideon"
MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "gideon"
MINIO_SECRET_KEY = "changeme"
MINIO_BUCKET = "gideon"

SCROLL_BATCH = 100  # points per scroll page


# ---------------------------------------------------------------------------
# MinIO helpers
# ---------------------------------------------------------------------------


def fetch_chunks_json(s3: Minio, firm_id: str, matter_id: str, document_id: str) -> list[dict]:
    """Return the full chunks list for a document from MinIO."""
    key = f"{firm_id}/{matter_id}/{document_id}/chunks.json"
    response = s3.get_object(MINIO_BUCKET, key)
    try:
        data = json.loads(response.read())
    finally:
        response.close()
        response.release_conn()
    return data["chunks"]


# ---------------------------------------------------------------------------
# Scroll helpers
# ---------------------------------------------------------------------------


def build_scroll_filter(firm_id: str | None, matter_id: str | None) -> models.Filter | None:
    must: list[models.FieldCondition] = []
    if firm_id:
        must.append(models.FieldCondition(key="firm_id", match=models.MatchValue(value=firm_id)))
    if matter_id:
        must.append(models.FieldCondition(key="matter_id", match=models.MatchValue(value=matter_id)))
    return models.Filter(must=must) if must else None


def scroll_all_points(
    client: QdrantClient,
    scroll_filter: models.Filter | None,
) -> list[models.ScoredPoint]:
    """Page through the collection and return all points (with payload)."""
    all_points: list = []
    offset = None

    while True:
        results, next_offset = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=scroll_filter,
            limit=SCROLL_BATCH,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        all_points.extend(results)
        if next_offset is None:
            break
        offset = next_offset

    return all_points


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill 'text' payload field on pre-Feature-7.3 Qdrant points."
    )
    parser.add_argument("--firm-id", default=None, help="Limit to a single firm UUID.")
    parser.add_argument("--matter-id", default=None, help="Limit to a single matter UUID.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be patched without writing anything.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Qdrant:  {QDRANT_URL}  collection={COLLECTION}")
    print(f"MinIO:   {MINIO_ENDPOINT}  bucket={MINIO_BUCKET}")
    if args.firm_id:
        print(f"Filter:  firm_id={args.firm_id}")
    if args.matter_id:
        print(f"         matter_id={args.matter_id}")
    if args.dry_run:
        print("Mode:    DRY RUN — no writes")
    print()

    qdrant = QdrantClient(
        url=QDRANT_URL,
        timeout=60,
        # Disable keep-alive pooling to avoid WinError 10054 on Windows
        limits=httpx.Limits(max_keepalive_connections=0, max_connections=10),
    )
    s3 = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )

    # 1. Scroll all points (optionally filtered by firm/matter)
    print("Scrolling points...", flush=True)
    scroll_filter = build_scroll_filter(args.firm_id, args.matter_id)
    all_points = scroll_all_points(qdrant, scroll_filter)
    print(f"Found {len(all_points)} total point(s).")

    # 2. Find points missing 'text'
    missing = [p for p in all_points if not (p.payload or {}).get("text")]
    print(f"Points missing 'text': {len(missing)}")

    if not missing:
        print("Nothing to patch.")
        return

    # 3. Group by (firm_id, matter_id, document_id) to batch MinIO fetches
    groups: dict[tuple[str, str, str], list] = defaultdict(list)
    for point in missing:
        p = point.payload or {}
        key = (str(p.get("firm_id", "")), str(p.get("matter_id", "")), str(p.get("document_id", "")))
        groups[key].append(point)

    print(f"Unique documents to fetch from MinIO: {len(groups)}")
    print(f"Estimated time: ~{len(missing) // 10}–{len(missing) // 5}s (10–20 points/sec on localhost)\n")

    # 4. For each document, fetch chunks.json and patch points
    patched = 0
    errors = 0
    doc_num = 0

    for (firm_id, matter_id, document_id), points in groups.items():
        doc_num += 1
        doc_short = document_id[:8]
        print(f"  [{doc_num}/{len(groups)}] doc={doc_short}  ({len(points)} chunk(s))...", end=" ", flush=True)

        try:
            chunks = fetch_chunks_json(s3, firm_id, matter_id, document_id)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            errors += len(points)
            continue

        # Build a lookup: chunk_index -> text
        chunk_text: dict[int, str] = {c["chunk_index"]: c["text"] for c in chunks}

        doc_patched = 0
        for point in points:
            p = point.payload or {}
            idx = int(p.get("chunk_index", 0))
            text = chunk_text.get(idx)

            if text is None:
                print(
                    f"\n  WARNING: chunk_index {idx} not found in chunks.json for doc {doc_short}",
                    file=sys.stderr,
                )
                errors += 1
                continue

            if not args.dry_run:
                qdrant.set_payload(
                    collection_name=COLLECTION,
                    payload={"text": text},
                    points=[point.id],
                    timeout=60,
                )

            patched += 1
            doc_patched += 1
            # Inline progress for large documents
            if doc_patched % 50 == 0:
                print(f"{doc_patched}...", end=" ", flush=True)

        print("done" if not args.dry_run else "dry-run")

    # 5. Summary
    print()
    if args.dry_run:
        print(f"Dry run complete. Would patch {patched} point(s).")
    else:
        print(f"Done. Patched {patched} point(s).")
    if errors:
        print(f"Errors: {errors} point(s) could not be patched — check stderr above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
