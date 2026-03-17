# OpenCase — Infrastructure Reference

Documents the Docker Compose setup in `infrastructure/`. See
[ARCHITECTURE.md](ARCHITECTURE.md) for the high-level service topology and
[SETTINGS.md](SETTINGS.md) for environment variable reference.

---

## Files

| File | Purpose |
| --- | --- |
| `infrastructure/docker-compose.yml` | Full development stack |
| `infrastructure/docker-compose.integration.yml` | Override for integration test runs |
| `infrastructure/postgres/init.sql` | Creates `opencase_test` DB on first startup |

---

## Running the Stack

```bash
# Start full development stack (from project root)
docker compose -f infrastructure/docker-compose.yml --env-file .env up

# Start in background
docker compose -f infrastructure/docker-compose.yml --env-file .env up -d

# Stop and remove containers (preserve volumes)
docker compose -f infrastructure/docker-compose.yml down

# Stop and wipe all volumes
docker compose -f infrastructure/docker-compose.yml down -v
```

Copy `.env.example` to `.env` and fill in the required values before first run.
At minimum, set `OPENCASE_AUTH_SECRET_KEY`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`.

---

## Services

### nextjs

Next.js frontend and reverse proxy.

| Setting | Value |
| --- | --- |
| Build context | `../frontend` |
| Public port | `3000` |
| Proxies to | `fastapi:8000` (internal) |
| Depends on | `fastapi` |

The Next.js container is the only service with a public port. FastAPI is
not directly reachable from outside the Docker network.

---

### fastapi

Python API server (uvicorn + FastAPI).

| Setting | Value |
| --- | --- |
| Build context | `../backend` |
| Dockerfile | `docker/Dockerfile` |
| Public port | `8000` (dev/test only — remove in production) |
| Internal port | `8000` |
| Depends on | `postgres` (healthy) |

The public port mapping (`8000:8000`) is present for local development and
integration tests. In production it should be removed — all external traffic
must route through Next.js.

---

### jaeger

Jaeger all-in-one distributed tracing collector.

| Setting | Value |
| --- | --- |
| Image | `jaegertracing/all-in-one:latest` |
| UI + REST query API | `16686` |
| OTLP gRPC receiver | `4317` |
| OTLP HTTP receiver | `4318` |
| Healthcheck | `wget -qO- http://localhost:16686/` |

Enabled by setting `OPENCASE_OTEL_ENABLED=true` and
`OPENCASE_OTEL_EXPORTER=otlp` on the `fastapi` service. The UI is available
at `http://localhost:16686`.

Jaeger does not ingest OTLP metrics (`/v1/metrics` returns 404). Metric
export errors in the FastAPI logs every 60 s are expected until an OTel
Collector is added.

---

### postgres

PostgreSQL 17 relational database.

| Setting | Value |
| --- | --- |
| Image | `postgres:17-alpine` |
| Public port | `${POSTGRES_PORT:-5432}:5432` |
| Volume | `postgres-data` |
| Init script | `infrastructure/postgres/init.sql` |
| Healthcheck | `pg_isready -U <user>` |

The init script runs once on first container startup and creates the
`opencase_test` database used by integration tests alongside the default
`opencase` database.

---

### qdrant

Qdrant vector store (single collection).

| Setting | Value |
| --- | --- |
| Image | `qdrant/qdrant:latest` |
| Internal port | `6333` |
| Volume | `qdrant-data` |

Only accessible from within the Docker network. Collection name is
controlled by `QDRANT_COLLECTION` (default: `opencase`).

---

### redis

Redis 7 task queue broker and cache.

| Setting | Value |
| --- | --- |
| Image | `redis:7-alpine` |
| Internal port | `6379` |
| Volume | `redis-data` |
| Healthcheck | `redis-cli ping` |

Used as the Celery broker. Not exposed outside the Docker network.

---

### minio

MinIO S3-compatible object store for original documents.

| Setting | Value |
| --- | --- |
| Image | `minio/minio:latest` |
| Internal API port | `9000` |
| Internal console port | `9001` |
| Volume | `minio-data` |
| Healthcheck | `mc ready local` |

Bucket name is controlled by `MINIO_BUCKET` (default: `opencase`).
Access credentials are set via `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`.

---

### ollama

Ollama local LLM and embedding server.

| Setting | Value |
| --- | --- |
| Image | `ollama/ollama:latest` |
| Internal port | `11434` |
| Volume | `ollama-models` |

Default LLM: `OLLAMA_LLM_MODEL` (default: `llama3:8b`).
Default embed model: `OLLAMA_EMBED_MODEL` (default: `nomic-embed-text`).

NVIDIA GPU acceleration is available — uncomment the `deploy.resources`
block in `docker-compose.yml` to enable it.

---

### celery-worker

Celery background task worker.

| Setting | Value |
| --- | --- |
| Build context | `../backend` |
| Dockerfile | `Dockerfile` |
| Command | `celery -A app.workers worker -l info` |
| Volume | `celery-tmp` (ephemeral temp files) |
| Depends on | `postgres` (healthy), `redis` (healthy), `minio` (healthy) |

Processes background tasks: document ingestion, embeddings, deadline
monitoring, audit chain validation, legal hold enforcement.

---

### celery-beat

Celery periodic task scheduler.

| Setting | Value |
| --- | --- |
| Build context | `../backend` |
| Dockerfile | `Dockerfile` |
| Command | `celery -A app.workers beat -l info` |
| Depends on | `redis` (healthy) |

Submits scheduled tasks on a cron-based schedule (cloud ingestion every
15 min, deadline monitor every hour, audit chain validator nightly).

---

## Volumes

| Volume | Service | Contents |
| --- | --- | --- |
| `postgres-data` | postgres | PostgreSQL data directory |
| `qdrant-data` | qdrant | Qdrant vector index and storage |
| `redis-data` | redis | Redis AOF persistence |
| `ollama-models` | ollama | Downloaded LLM and embedding models |
| `minio-data` | minio | Object store buckets and objects |
| `celery-tmp` | celery-worker | Ephemeral temp files during ingestion |

All volumes are named (managed by Docker). Deleting volumes wipes the
corresponding data permanently.

---

## Port Map

| Port | Service | Access |
| --- | --- | --- |
| `3000` | Next.js | Public — browser entry point |
| `8000` | FastAPI | Dev/test only — remove in production |
| `5432` | PostgreSQL | Dev/test only |
| `16686` | Jaeger UI | Dev/test only |
| `4317` | Jaeger OTLP gRPC | Internal (Docker network) |
| `4318` | Jaeger OTLP HTTP | Internal (Docker network) |

All other services (Qdrant, Redis, MinIO, Ollama, Celery) are internal
only and not mapped to host ports.

---

## Integration Test Stack

`infrastructure/docker-compose.integration.yml` is a Compose override used
automatically by `pytest-docker` (configured in `backend/tests/conftest.py`).

**Changes from base stack:**

- `fastapi` points at `opencase_test` database (created by `init.sql`)
- `fastapi` has OTel enabled (`EXPORTER=otlp`, targeting `jaeger:4318`)
- All unimplemented services are disabled via Docker Compose profiles:
  `nextjs`, `celery-worker`, `celery-beat`, `minio`, `ollama`, `qdrant`, `redis`
- Active services: `postgres` + `fastapi` + `jaeger`

To run integration tests:

```bash
cd backend
uv run pytest -m integration
```

pytest-docker starts the stack before tests and tears it down with `-v`
afterward so the test database is wiped between runs.
