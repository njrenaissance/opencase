# Gideon — Copilot

Self-hostable discovery platform for criminal defense. All on-premise.

## Standards

[docs/coding_standards/](../docs/coding_standards/) — See Gideon Essentials for security rules.

**Must enforce:**

- No third-party LLM API calls
- No external telemetry
- Legal hold = immutable
- `build_permissions_filter()` on every Qdrant query

## Setup

```bash
uv sync && uv run pytest backend/tests/
```
