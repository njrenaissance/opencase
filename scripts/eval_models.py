#!/usr/bin/env python3
"""Evaluate an exported RAG prompt against multiple Ollama models.

Takes a prompt JSON file produced by ``scripts/rag_query.py --export-prompt``
and runs the same assembled messages through each specified model.  With
``--baseline``, each model is run twice — once with the full RAG context
and once with the bare question (no retrieved documents) — so you can measure
whether retrieval actually helps.

Usage:
    python scripts/eval_models.py prompt.json --models llama3,mistral

    # RAG vs baseline comparison:
    python scripts/eval_models.py prompt.json \\
        --models llama3,mistral \\
        --baseline \\
        --output results.json

    # Inspect the exported prompt without running inference:
    python scripts/eval_models.py prompt.json --inspect

Optional flags:
    --models MODEL,...     Comma-separated Ollama model names to evaluate
    --baseline             Also run each model without RAG context (bare question)
    --output PATH          Write comparison results to JSON (default: none)
    --max-tokens N         Max tokens per response (default: -2, fill context)
    --inspect              Print the exported prompt and exit — no inference
    --no-stream            Collect each full response before printing
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
DEFAULT_MAX_TOKENS = -2
DEFAULT_MODELS = "llama3"


# ---------------------------------------------------------------------------
# Ollama helpers (urllib only — avoids WinError 10054 on localhost)
# ---------------------------------------------------------------------------


def _post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def call_ollama_blocking(
    model: str,
    messages: list[dict],
    max_tokens: int,
) -> str:
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


def call_ollama_stream(
    model: str,
    messages: list[dict],
    max_tokens: int,
) -> str:
    """Stream response from Ollama, print tokens as they arrive, return full text."""
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


def _run(model: str, messages: list[dict], max_tokens: int, no_stream: bool) -> str:
    """Run inference and return the full response text."""
    try:
        if no_stream:
            return call_ollama_blocking(model, messages, max_tokens)
        else:
            return call_ollama_stream(model, messages, max_tokens)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return f"ERROR: {exc}"


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------


def _build_baseline_messages(messages: list[dict]) -> list[dict]:
    """Strip the RAG context block from the user message, leaving just the question.

    The user message assembled by rag_query.py has the form:
        "Context from case documents:\n\n<context>\n\nQuestion: <query>"

    The baseline replaces that with just the bare question so the model must
    answer from its own weights — no retrieved documents provided.
    """
    baseline = []
    for msg in messages:
        if msg.get("role") == "user":
            content = msg["content"]
            # Extract the question from "... \n\nQuestion: <query>"
            marker = "\n\nQuestion: "
            idx = content.rfind(marker)
            bare_question = content[idx + len(marker):] if idx != -1 else content
            baseline.append({"role": "user", "content": bare_question})
        else:
            baseline.append(msg)
    return baseline


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate an exported RAG prompt against multiple Ollama models."
    )
    parser.add_argument(
        "prompt_file",
        metavar="PROMPT_FILE",
        help="Path to a prompt JSON file produced by rag_query.py --export-prompt.",
    )
    parser.add_argument(
        "--models",
        default=DEFAULT_MODELS,
        help=f"Comma-separated Ollama model names (default: {DEFAULT_MODELS}).",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help=(
            "Also run each model without RAG context (bare question only). "
            "Lets you measure whether retrieval actually improves the answer."
        ),
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help="Write comparison results to JSON file.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Max tokens per response (default: {DEFAULT_MAX_TOKENS}, -2 = fill context).",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Print the prompt contents and exit — no inference.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Collect each full response before printing.",
    )
    return parser.parse_args()


def _print_prompt(prompt: dict) -> None:
    """Pretty-print the exported prompt for inspection."""
    print("=" * 60)
    print("PROMPT METADATA")
    print("=" * 60)
    print(f"  Query:      {prompt.get('query')}")
    print(f"  Matter ID:  {prompt.get('matter_id')}")
    print(f"  Firm ID:    {prompt.get('firm_id')}")
    print(f"  Top-K:      {prompt.get('top_k')}")
    excluded = prompt.get("excluded_classifications") or []
    if excluded:
        print(f"  Excluded:   {', '.join(excluded)}")

    hits = prompt.get("retrieval_hits", [])
    print(f"\n  Retrieved {len(hits)} chunk(s):")
    for i, h in enumerate(hits, 1):
        doc = str(h.get("document_id", ""))[:8]
        score = h.get("score", 0)
        chunk = h.get("chunk_index")
        cls = h.get("classification")
        bates = h.get("bates_number") or ""
        page = h.get("page_number")
        parts = [f"doc={doc}", f"chunk={chunk}", f"score={score:.4f}", f"class={cls}"]
        if bates:
            parts.append(f"bates={bates}")
        if page is not None:
            parts.append(f"page={page}")
        print(f"    [{i}] {' | '.join(parts)}")

    messages = prompt.get("messages", [])
    print(f"\n  Messages ({len(messages)}):")
    for msg in messages:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        preview = content[:200].replace("\n", " ")
        ellipsis = "…" if len(content) > 200 else ""
        print(f"\n  [{role.upper()}]\n  {preview}{ellipsis}")
    print()


def main() -> None:
    args = parse_args()
    prompt_path = Path(args.prompt_file)

    if not prompt_path.exists():
        print(f"ERROR: File not found: {prompt_path}", file=sys.stderr)
        sys.exit(1)

    try:
        prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: Could not read prompt file: {exc}", file=sys.stderr)
        sys.exit(1)

    _print_prompt(prompt)

    if args.inspect:
        return

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    rag_messages = prompt.get("messages", [])
    if not rag_messages:
        print("ERROR: Prompt file contains no messages.", file=sys.stderr)
        sys.exit(1)

    baseline_messages = _build_baseline_messages(rag_messages) if args.baseline else None

    mode_desc = "RAG + baseline" if args.baseline else "RAG only"
    print(f"Running {mode_desc} against {len(models)} model(s): {', '.join(models)}\n")

    results: list[dict] = []

    for model in models:
        result: dict = {"model": model}

        # --- RAG response ---
        print("=" * 60)
        print(f"MODEL: {model}  |  WITH RAG CONTEXT")
        print("=" * 60)
        result["rag_response"] = _run(model, rag_messages, args.max_tokens, args.no_stream)
        print()

        # --- Baseline response (no context) ---
        if baseline_messages is not None:
            print("=" * 60)
            print(f"MODEL: {model}  |  BASELINE (no context)")
            print("=" * 60)
            result["baseline_response"] = _run(
                model, baseline_messages, args.max_tokens, args.no_stream
            )
            print()

        results.append(result)

    if args.output:
        output_path = Path(args.output)
        comparison = {
            "prompt_file": str(prompt_path.resolve()),
            "query": prompt.get("query"),
            "matter_id": prompt.get("matter_id"),
            "retrieval_hits": prompt.get("retrieval_hits", []),
            "baseline_enabled": args.baseline,
            "results": results,
        }
        output_path.write_text(
            json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Results saved → {output_path.resolve()}")


if __name__ == "__main__":
    main()
