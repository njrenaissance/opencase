# Gideon Backend

FastAPI application powering the Gideon API, RAG
pipeline, and background workers.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (package manager)

## Setup

```bash
cd backend
uv venv
uv sync
```

## Running

```bash
uv run uvicorn app.main:app --reload --port 8000
```

## Testing

```bash
uv run pytest
uv run pytest --cov=app
```

## Linting & Formatting

```bash
uv run ruff check .
uv run ruff format .
uv run mypy app/
```

## Project Structure

```text
app/
├── api/            # FastAPI routers
├── core/           # Auth, permissions, audit
├── rag/            # LangChain RAG pipeline
├── ingestion/      # Document parsing, chunking, dedup
├── storage/        # MinIO S3 client
├── workers/        # Celery tasks
└── db/             # SQLAlchemy models, session
tests/
├── features/       # Gherkin .feature files
└── step_defs/      # pytest-bdd step definitions
```

## Key Commands

| Task | Command |
| --- | --- |
| Install deps | `uv sync` |
| Run server | `uv run uvicorn app.main:app --reload` |
| Run tests | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type check | `uv run mypy app/` |
