#!/usr/bin/env python3
"""Query an Ollama model directly — no RAG, no Qdrant, no embedding.

Sends the system prompt + a bare question to Ollama and streams the response.
Use this as a baseline to compare against rag_query.py results, or to test
model behaviour and system prompt changes in isolation.

Usage:
    python scripts/query_model.py "What Brady material exists for the defendant?"

Optional flags:
    --model MODEL          Ollama model name (default: llama3)
    --system-prompt TEXT   Override the system prompt inline
    --no-stream            Collect full response before printing
    --max-tokens N         Max tokens to generate (default: -2, fill context)
    --export PATH          Save the request + response to JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _ollama import OLLAMA_URL, call_ollama_blocking, call_ollama_stream

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "llama3"
DEFAULT_MAX_TOKENS = -2

SYSTEM_PROMPT_PATH = Path("/app/SYSTEM_PROMPT.md")
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query an Ollama model directly — no RAG context."
    )
    parser.add_argument("query", nargs="+", help="The question to ask.")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model name (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--system-prompt",
        default=None,
        metavar="TEXT",
        help="Override the system prompt inline (default: load from SYSTEM_PROMPT.md).",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Collect full response before printing.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Max tokens to generate (default: {DEFAULT_MAX_TOKENS}, -2 = fill context).",
    )
    parser.add_argument(
        "--export",
        metavar="PATH",
        default=None,
        help="Save the request and response to a JSON file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    query = " ".join(args.query)
    system_prompt = args.system_prompt or load_system_prompt()

    print(f'Query:  "{query}"')
    print(f"Model:  {args.model}")
    print(f"Mode:   direct (no RAG context)")
    print()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    print("=" * 60)
    print("RESPONSE")
    print("=" * 60)

    try:
        if args.no_stream:
            response = call_ollama_blocking(args.model, messages, args.max_tokens)
            print(response)
        else:
            response = call_ollama_stream(args.model, messages, args.max_tokens)
    except Exception as exc:
        print(f"\nERROR: Ollama inference failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.export:
        export_path = Path(args.export)
        export_path.write_text(
            json.dumps(
                {
                    "query": query,
                    "model": args.model,
                    "mode": "direct",
                    "messages": messages,
                    "response": response,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"\nExported → {export_path.resolve()}")


if __name__ == "__main__":
    main()
