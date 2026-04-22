#!/usr/bin/env python3
"""Shared Ollama HTTP helpers for scripts.

Provides low-level functions for calling Ollama's /api/chat endpoint.
Used by eval_models.py, query_model.py, and rag_query.py.
"""

from __future__ import annotations

import json
import urllib.request

OLLAMA_URL = "http://localhost:11434"


def _post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    """POST JSON to a URL and return the parsed response."""
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
    timeout: int = 300,
) -> str:
    """Call Ollama /api/chat without streaming. Returns full response."""
    result = _post_json(
        f"{OLLAMA_URL}/api/chat",
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        },
        timeout=timeout,
    )
    return result["message"]["content"]


def call_ollama_stream(
    model: str,
    messages: list[dict],
    max_tokens: int,
    timeout: int = 300,
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
    with urllib.request.urlopen(req, timeout=timeout) as resp:
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
