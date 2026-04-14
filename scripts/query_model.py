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
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434"
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


def _post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def call_ollama_blocking(model: str, messages: list[dict], max_tokens: int) -> str:
    result = _post_json(
        f"{OLLAMA_URL}/api/chat",
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        },
        timeout=300,
    )
    return result["message"]["content"]


def call_ollama_stream(model: str, messages: list[dict], max_tokens: int) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    parts: list[str] = []
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
                parts.append(token)
            if data.get("done"):
                break
    print()
    return "".join(parts)


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
