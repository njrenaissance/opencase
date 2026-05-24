#!/usr/bin/env python3
"""End-to-end RAG query against the Gideon stack.

Runs inside the FastAPI container so it can reach Ollama and Qdrant
on the Docker network.  Embeds a query, searches Qdrant (with an
optional classification exclusion filter), prints the retrieved context
block, then calls Ollama for inference and streams the response.

Usage (from repo root):
    docker exec gideon-fastapi-1 python scripts/rag_query.py \\
        --matter-id <uuid> \\
        --firm-id <uuid> \\
        "What Brady material exists for the defendant?"

Optional flags:
    --top-k N              Number of chunks to retrieve (default: 5)
    --model MODEL          Ollama model name (default: llama3)
    --exclude CLASS,...    Comma-separated classifications to exclude
                           e.g. --exclude jencks,work_product
    --no-stream            Collect full response before printing
    --export-prompt PATH   Save assembled messages to JSON (before inference)
    --no-infer             Stop after prompt assembly — no Ollama call

The --export-prompt JSON can be passed to scripts/eval_models.py to run
the same prompt against multiple models for evaluation.

Note: This script bypasses the FastAPI auth layer and build_qdrant_filter.
It is a developer tool only — never expose it in production.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import httpx
from qdrant_client import QdrantClient, models
from qdrant_client.models import FieldCondition, MatchAny, MatchValue

from _ollama import OLLAMA_URL

# ---------------------------------------------------------------------------
# Constants — mirror defaults from app/core/config.py
# ---------------------------------------------------------------------------

QDRANT_URL = "http://127.0.0.1:6333"
COLLECTION = "gideon"
EMBEDDING_MODEL = "nomic-embed-text:v1.5"
DEFAULT_MODEL = "llama3"
DEFAULT_TOP_K = 3
# System matter UUIDs (from app/core/constants.py)
DEFAULT_MATTER_ID = "00000000-0000-0000-0000-000000000001"  # GLOBAL_KNOWLEDGE_MATTER_ID
DEFAULT_FIRM_ID = "4cad8128-9692-4ab3-91d3-c53a2620d2a5"
# -2 = fill context window; matches Ollama behaviour when no limit is wanted.
# Override with --max-tokens if you want a hard cap.
DEFAULT_MAX_TOKENS = -2
# Minimum chunk text length (characters) — filters out headers, citations, tiny snippets
# With neighboring chunk expansion, can be more permissive
# Set to 0 to disable filtering
MIN_CHUNK_TEXT_LENGTH = 0

SYSTEM_PROMPT_PATH = Path("./backend/SYSTEM_PROMPT.md")
_DEFAULT_SYSTEM_PROMPT = (
    "You are Gideon, a legal discovery assistant for criminal defense attorneys. "
    "Answer questions based only on the documents retrieved for this matter. "
    "If the answer is not in the provided context, say so clearly. "
    "Always cite your sources."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.exists():
        content = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
        if content:
            return content
    return _DEFAULT_SYSTEM_PROMPT


def embed_query(query: str) -> list[float]:
    # Use httpx with keep-alive disabled to avoid WinError 10054 on Windows
    with httpx.Client(
        limits=httpx.Limits(max_keepalive_connections=0, max_connections=10),
        timeout=300,
    ) as client:
        resp = client.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBEDDING_MODEL, "input": [query]},
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]


def build_filter(
    firm_id: str,
    matter_id: str,
    excluded_classifications: list[str],
) -> models.Filter:
    must = [
        FieldCondition(key="firm_id", match=MatchValue(value=firm_id)),
        FieldCondition(key="matter_id", match=MatchAny(any=[matter_id])),
    ]
    must_not: list[FieldCondition] = []
    if excluded_classifications:
        must_not = [
            FieldCondition(
                key="classification",
                match=MatchAny(any=excluded_classifications),
            )
        ]
    return models.Filter(must=must, must_not=must_not)


def search_qdrant(
    client: QdrantClient,
    vector: list[float],
    qdrant_filter: models.Filter,
    limit: int,
) -> list[models.ScoredPoint]:
    result = client.query_points(
        collection_name=COLLECTION,
        query=vector,
        query_filter=qdrant_filter,
        limit=limit,
        with_payload=True,
    )
    return result.points


def expand_with_neighbors(
    client: QdrantClient,
    hits: list[models.ScoredPoint],
) -> list[models.ScoredPoint]:
    """For each hit, fetch neighboring chunks (N-1, N, N+1) from same document.

    Returns all chunks (original + neighbors) grouped by document and sorted by index.
    """
    expanded: dict[str, list[models.ScoredPoint]] = {}

    for hit in hits:
        doc_id = str((hit.payload or {}).get("document_id", ""))
        chunk_idx = (hit.payload or {}).get("chunk_index", 0)

        if doc_id not in expanded:
            expanded[doc_id] = []

        # Fetch this chunk and its neighbors
        for offset in [-1, 0, 1]:
            neighbor_idx = chunk_idx + offset
            if neighbor_idx < 0:
                continue

            # Build point ID (same logic as backend)
            import uuid
            point_id_ns = uuid.UUID("b6e7f2a1-4c3d-4e8f-9a1b-2d3e4f5a6b7c")
            neighbor_point_id = str(uuid.uuid5(point_id_ns, f"{doc_id}:{neighbor_idx}"))

            try:
                result = client.retrieve(COLLECTION, ids=[neighbor_point_id], with_payload=True)
                if result:
                    expanded[doc_id].extend(result)
            except Exception:
                pass  # Chunk doesn't exist

    # Flatten, deduplicate by point ID, sort by chunk_index
    all_chunks: dict[str, models.ScoredPoint] = {}
    for doc_chunks in expanded.values():
        for chunk in doc_chunks:
            all_chunks[chunk.id] = chunk

    # Sort by document_id, then chunk_index
    result_list = sorted(
        all_chunks.values(),
        key=lambda c: (
            str((c.payload or {}).get("document_id", "")),
            (c.payload or {}).get("chunk_index", 0),
        ),
    )
    return result_list


def format_context(chunks: list[models.ScoredPoint], filenames: dict[str, str] | None = None) -> str:
    if not chunks:
        return "No relevant documents were found for this query."
    filenames = filenames or {}
    parts: list[str] = []
    for i, point in enumerate(chunks, 1):
        p = point.payload or {}
        doc_id = str(p.get("document_id", ""))
        page = p.get("page_number")
        bates = p.get("bates_number")
        # Text is stored directly in the Qdrant payload (Feature 7.3+).
        # Older points without 'text' fall back to a placeholder.
        text = str(p.get("text") or "(chunk text not in payload — re-ingest document)")

        filename = filenames.get(doc_id, "unknown")
        header_parts = [f"Source {i}", f"File: {filename}"]
        if page is not None:
            header_parts.append(f"Page: {page}")
        if bates:
            header_parts.append(f"Bates: {bates}")

        parts.append(f"[{' | '.join(header_parts)}]\n{text}")
    return "\n\n".join(parts)


def call_ollama_stream(
    model: str,
    system_prompt: str,
    context: str,
    query: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> None:
    """Call Ollama /api/chat with streaming and print tokens as they arrive."""
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Context from case documents:\n\n{context}\n\nQuestion: {query}",
        },
    ]
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"num_predict": max_tokens},
        }
    ).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        for raw_line in resp:
            line = raw_line.decode().strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            token = data.get("message", {}).get("content", "")
            if token:
                print(token, end="", flush=True)
            if data.get("done"):
                break
    print()  # final newline


def call_ollama_blocking(
    model: str,
    system_prompt: str,
    context: str,
    query: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Call Ollama /api/chat without streaming. Returns full response."""
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Context from case documents:\n\n{context}\n\nQuestion: {query}",
        },
    ]
    with httpx.Client(
        limits=httpx.Limits(max_keepalive_connections=0, max_connections=10),
        timeout=120,
    ) as client:
        resp = client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG query against the Gideon stack (dev/debug tool).")
    parser.add_argument("query", nargs="+", help="The query text.")
    parser.add_argument(
        "--matter-id",
        default=DEFAULT_MATTER_ID,
        help=f"Matter UUID to query (default: {DEFAULT_MATTER_ID}).",
    )
    parser.add_argument(
        "--firm-id",
        default=DEFAULT_FIRM_ID,
        help=f"Firm UUID to filter by (default: {DEFAULT_FIRM_ID}).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Number of chunks to retrieve (default: {DEFAULT_TOP_K}).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model name (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="Comma-separated classifications to exclude (e.g. jencks,work_product).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=(f"Max tokens to generate (default: {DEFAULT_MAX_TOKENS}, -2 = fill context, -1 = infinite)."),
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Collect full response before printing (useful for piping).",
    )
    parser.add_argument(
        "--export-prompt",
        metavar="PATH",
        default=None,
        help=(
            "Save the fully assembled messages (system + context + query) to a JSON "
            "file before calling Ollama. Pass this file to scripts/eval_models.py "
            "to benchmark the same prompt against multiple models."
        ),
    )
    parser.add_argument(
        "--no-infer",
        action="store_true",
        help="Stop after prompt assembly — skip the Ollama call entirely. "
        "Useful with --export-prompt to inspect prompts for private data.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    query = " ".join(args.query)
    excluded = [c.strip() for c in args.exclude.split(",") if c.strip()]

    print(f'Query:     "{query}"')
    print(f"Matter ID: {args.matter_id}")
    print(f"Firm ID:   {args.firm_id}")
    print(f"Top-K:     {args.top_k}")
    print(f"Model:     {args.model}")
    if excluded:
        print(f"Excluded:  {', '.join(excluded)}")
    if args.export_prompt:
        print(f"Export:    {args.export_prompt}")
    if args.no_infer:
        print("Mode:      prompt assembly only — no inference")
    print()

    # 1. Embed query
    print("Embedding query...", flush=True)
    try:
        vector = embed_query(query)
    except Exception as exc:
        print(f"ERROR: Failed to embed query: {exc}", file=sys.stderr)
        sys.exit(1)

    # 2. Build filter and search Qdrant
    print("Searching Qdrant...", flush=True)
    try:
        client = QdrantClient(
            url=QDRANT_URL,
            timeout=60,
            # Disable keep-alive pooling to avoid WinError 10054 on Windows
            limits=httpx.Limits(max_keepalive_connections=0, max_connections=10),
        )
        qdrant_filter = build_filter(args.firm_id, args.matter_id, excluded)
        hits = search_qdrant(client, vector, qdrant_filter, args.top_k)
    except Exception as exc:
        print(f"ERROR: Qdrant search failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Filter out tiny chunks (headers, citations, etc.)
    hits = [
        h for h in hits
        if len(str((h.payload or {}).get("text", ""))) >= MIN_CHUNK_TEXT_LENGTH
    ]

    print(f"Retrieved {len(hits)} chunk(s) (min {MIN_CHUNK_TEXT_LENGTH} chars).")

    # De-duplicate by document — keep only top-scoring chunk from each
    print("De-duplicating by document...", flush=True)
    hits_by_doc: dict[str, models.ScoredPoint] = {}
    for hit in hits:
        doc_id = str((hit.payload or {}).get("document_id", ""))
        if doc_id not in hits_by_doc or hit.score > hits_by_doc[doc_id].score:
            hits_by_doc[doc_id] = hit

    hits = sorted(hits_by_doc.values(), key=lambda h: h.score, reverse=True)
    print(f"De-duplicated to {len(hits)} unique documents.")

    # Expand with neighboring chunks (N-1, N, N+1)
    print("Expanding with neighboring chunks...", flush=True)
    hits = expand_with_neighbors(client, hits)
    print(f"Expanded to {len(hits)} total chunks.\n")

    # 3. Build filename map from Qdrant payload
    filenames = {
        str((h.payload or {}).get("document_id", "")): str((h.payload or {}).get("filename", "unknown")) for h in hits
    }

    # 4. Print retrieved context so developer can see what the model receives
    context = format_context(hits, filenames)
    print("=" * 60)
    print("RETRIEVED CONTEXT")
    print("=" * 60)
    print(context)
    print()

    # 5. Print each result's metadata summary
    for i, hit in enumerate(hits, 1):
        p = hit.payload or {}
        if p.get("document_id", "")[:8] == "9ae29c3a":
            print(
                f"  [{i}] score={hit.score:.4f} | doc={str(p.get('document_id', ''))[:8]}"
                f" | chunk={p.get('chunk_index')} | class={p.get('classification')}"
            )
    print()

    # 6. Assemble prompt
    system_prompt = load_system_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Context from case documents:\n\n{context}\n\nQuestion: {query}",
        },
    ]

    # 6a. Export prompt JSON if requested
    if args.export_prompt:
        export_path = Path(args.export_prompt)
        prompt_export = {
            "query": query,
            "matter_id": args.matter_id,
            "firm_id": args.firm_id,
            "top_k": args.top_k,
            "excluded_classifications": excluded,
            "retrieval_hits": [
                {
                    "score": round(h.score, 6),
                    "document_id": str((h.payload or {}).get("document_id", "")),
                    "chunk_index": (h.payload or {}).get("chunk_index"),
                    "classification": (h.payload or {}).get("classification"),
                    "bates_number": (h.payload or {}).get("bates_number"),
                    "page_number": (h.payload or {}).get("page_number"),
                }
                for h in hits
            ],
            "messages": messages,
        }
        export_path.write_text(json.dumps(prompt_export, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nPrompt exported → {export_path.resolve()}")

    if args.no_infer:
        return

    # 6b. Run inference
    print("=" * 60)
    print("LLM RESPONSE")
    print("=" * 60)
    try:
        if args.no_stream:
            response = call_ollama_blocking(args.model, system_prompt, context, query, args.max_tokens)
            print(response)
        else:
            call_ollama_stream(args.model, system_prompt, context, query, args.max_tokens)
    except Exception as exc:
        print(f"\nERROR: Ollama inference failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
