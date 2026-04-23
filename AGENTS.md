# Gideon

Self-hostable discovery platform for criminal defense practitioners.
All code on-premise; no third-party LLM APIs.

## Standards

See [docs/coding_standards/](docs/coding_standards/) for complete standards.

**Key rules:** No third-party LLM API calls • No external telemetry • Legal hold = immutable • `build_permissions_filter()` on every Qdrant query

## Security Non-Negotiables

1. No third-party LLM API calls — Ollama only
2. No model training on client data
3. No external telemetry
4. **`build_permissions_filter()` wraps every Qdrant query** — no exceptions
5. Legal hold documents are immutable
6. SHA-256 hash every document
7. Immutable audit log

## Setup

```bash
uv sync
uv run ruff format backend/
uv run ruff check backend/
uv run pytest backend/tests/
```

## Documentation

[docs/](docs/) — Full reference including architecture, auth, deployment, legal compliance
