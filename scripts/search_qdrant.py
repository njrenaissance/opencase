#!/usr/bin/env python3
"""Quick semantic search against the Gideon Qdrant vector store.

Runs inside the FastAPI container so it can reach Ollama and Qdrant
on the Docker network. Embeds a query, searches Qdrant, then pulls
chunk text from MinIO.

Usage (from repo root):
    docker exec gideon-fastapi-1 python /app/scripts/search_qdrant.py "your query here"

Or mount and run:
    docker exec gideon-fastapi-1 python scripts/search_qdrant.py "Explain the purpose of Gideon"
"""

from __future__ import annotations

import json
import sys

import httpx
from minio import Minio  # type: ignore[import-untyped]

OLLAMA_URL = "http://ollama:11434"
QDRANT_URL = "http://qdrant:6333"
COLLECTION = "gideon"
MINIO_ENDPOINT = "minio:9000"
MINIO_ACCESS_KEY = "gideon"
MINIO_SECRET_KEY = "changeme"
MINIO_BUCKET = "gideon"
EMBEDDING_MODEL = "nomic-embed-text"
TOP_K = 3


def embed_query(query: str) -> list[float]:
    resp = httpx.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBEDDING_MODEL, "input": [query]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"][0]


def search_qdrant(vector: list[float], limit: int = TOP_K) -> list[dict]:
    resp = httpx.post(
        f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
        json={"vector": vector, "limit": limit, "with_payload": True},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["result"]


def fetch_chunk_text(
    s3: Minio, firm_id: str, matter_id: str, document_id: str, chunk_index: int
) -> str:
    key = f"{firm_id}/{matter_id}/{document_id}/chunks.json"
    response = s3.get_object(MINIO_BUCKET, key)
    try:
        data = json.loads(response.read())
    finally:
        response.close()
        response.release_conn()
    return data["chunks"][chunk_index]["text"]


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: search_qdrant.py <query>", file=sys.stderr)
        sys.exit(1)

    query = " ".join(sys.argv[1:])

    print(f'Query: "{query}"')
    print()

    vector = embed_query(query)
    hits = search_qdrant(vector)

    s3 = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )

    for i, hit in enumerate(hits, 1):
        score = hit["score"]
        p = hit["payload"]

        try:
            text = fetch_chunk_text(
                s3, p["firm_id"], p["matter_id"], p["document_id"], p["chunk_index"]
            )
        except Exception as e:
            text = f"(could not load chunk: {e})"

        print(f"--- Result {i} [score={score:.4f}] ---")
        print(f"Document:       {p['document_id']}")
        print(f"Chunk:          {p['chunk_index']}")
        print(f"Classification: {p['classification']}")
        print(f"Source:         {p['source']}")
        if p.get("bates_number"):
            print(f"Bates:          {p['bates_number']}")
        print()
        print(text)
        print()


if __name__ == "__main__":
    main()
