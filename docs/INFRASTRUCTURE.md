# Gideon — Infrastructure Reference

Documents the Docker Compose setup in `infrastructure/`. See
[ARCHITECTURE.md](ARCHITECTURE.md) for the high-level service topology and
[SETTINGS.md](SETTINGS.md) for environment variable reference.

---

## Files

| File | Purpose |
| --- | --- |
| `infrastructure/docker-compose.yml` | Full development stack |
| `infrastructure/docker-compose.integration.yml` | Override for integration test runs |
| `infrastructure/postgres/init.sql` | Creates `gideon_tasks`, `gideon_test`, and `gideon_tasks_test` DBs on first startup |

---

## Running the Stack

### Development stack

The dev stack uses `.env` at the project root and starts the services
needed for local development: PostgreSQL, Redis, MinIO, FastAPI,
Celery worker + beat, Flower, and Grafana.

Next.js is disabled via Docker Compose profiles and will not start
until frontend implementation begins.

```bash
# Start development stack (from project root)
docker compose -f infrastructure/docker-compose.yml --env-file .env up

# Start in background
docker compose -f infrastructure/docker-compose.yml --env-file .env up -d

# Stop and remove containers (preserve volumes)
docker compose -f infrastructure/docker-compose.yml --env-file .env down

# Stop and wipe all volumes (clean slate)
docker compose -f infrastructure/docker-compose.yml --env-file .env down -v
```

Before first run, create the persistent Ollama model cache volume:

```bash
docker volume create gideon-ollama-models
```

This volume is declared external and is never deleted by `docker compose down -v`.

Copy `.env.example` to `.env` and fill in the required values before first run.
At minimum, set `GIDEON_AUTH_SECRET_KEY`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `GIDEON_S3_ACCESS_KEY`, and
`GIDEON_S3_SECRET_KEY`.

To enable the frontend when ready:

```bash
# Enable frontend (Next.js)
docker compose -f infrastructure/docker-compose.yml --env-file .env --profile frontend up
```

### Integration test stack

The test stack uses `backend/.env.test` and is managed automatically by
`pytest-docker`. It overlays `docker-compose.integration.yml` on top of the
base compose file, which points FastAPI and Celery at the `gideon_test`
and `gideon_tasks_test` databases (created by `postgres/init.sql`).

Flower is additionally disabled for tests. Volumes are wiped on teardown
so each run starts from a clean database.

```bash
# Run integration tests (pytest-docker starts/stops the stack)
cd backend
uv run pytest -m integration

# Run a specific integration test file
cd backend
uv run pytest -m integration tests/test_document_upload_integration.py -v
```

You do not need to start or stop Docker manually — `pytest-docker`
handles the full lifecycle. The test stack uses a separate project name
(`gideon-test`) so it does not conflict with a running dev stack.

---

## Services

### celery-beat

Celery periodic task scheduler.

| Setting | Value |
| --- | --- |
| Build context | `..` (repo root) |
| Dockerfile | `backend/docker/Dockerfile` |
| Command | `celery -A app.workers beat -l info --schedule /tmp/celery/celerybeat-schedule` |
| Volume | `celery-tmp` (schedule file persistence) |
| Depends on | `redis` (healthy) |

Submits scheduled tasks on a cron-based schedule (cloud ingestion every
15 min, deadline monitor every hour, audit chain validator nightly).
Migrations are skipped (`SKIP_MIGRATIONS=true`).

---

### celery-worker

Celery background task worker.

| Setting | Value |
| --- | --- |
| Build context | `..` (repo root) |
| Dockerfile | `backend/docker/Dockerfile` |
| Command | `celery -A app.workers worker -l info` |
| Volume | `celery-tmp` (ephemeral temp files) |
| Depends on | `postgres` (healthy), `redis` (healthy), `minio-init` (completed), `tika` (healthy), `qdrant-init` (completed), `ollama-init` (completed) |

Processes background tasks: document ingestion, embeddings, deadline
monitoring, audit chain validation, legal hold enforcement. Migrations
are skipped (`SKIP_MIGRATIONS=true`). See [TASKS.md](TASKS.md) for the
task registry and Celery architecture.

---

### db-migrate

Runs Alembic migrations then exits. This is a one-shot init container — it
does not stay running.

| Setting | Value |
| --- | --- |
| Build context | `../backend` |
| Dockerfile | `docker/Dockerfile` |
| Command | `["true"]` (entrypoint runs migrations, then `exec true` exits) |
| Depends on | `postgres` (healthy) |
| Restart | `no` |

Admin user seeding was previously handled by this container. It has moved to
the FastAPI lifespan hook (see `GIDEON_ADMIN_*` env vars in
[SETTINGS.md](SETTINGS.md)).

---

### fastapi

Python API server (uvicorn + FastAPI).

| Setting | Value |
| --- | --- |
| Build context | `..` (repo root) |
| Dockerfile | `backend/docker/Dockerfile` |
| Public port | `8000` (dev/test only — remove in production) |
| Internal port | `8000` |
| Depends on | `db-migrate` (completed), `redis` (healthy), `minio-init` (completed), `qdrant-init` (completed), `ollama-init` (completed) |

The public port mapping (`8000:8000`) is present for local development and
integration tests. In production it should be removed — all external traffic
must route through Next.js.

On startup the lifespan hook seeds the initial admin user if
`GIDEON_ADMIN_EMAIL` and `GIDEON_ADMIN_PASSWORD` are set. The seed is
idempotent and reuses the app's existing database connection pool.

---

### flower

Flower — Celery monitoring web UI for real-time task and worker visibility.

| Setting | Value |
| --- | --- |
| Build context | `..` (repo root) |
| Dockerfile | `backend/docker/Dockerfile` |
| Command | `celery -A app.workers flower --port=5555 --url_prefix=/flower` |
| Public port | `${GIDEON_FLOWER_PORT:-5555}:5555` |
| Depends on | `redis` (healthy) |

Provides a dashboard showing queue depth, worker status, active/completed
tasks, and task details. Basic auth is configurable via
`GIDEON_FLOWER_BASIC_AUTH` (format: `user:password`). OTel is disabled
for Flower — it is a monitoring UI, not a task producer.

---

### grafana (otel-lgtm)

Grafana otel-lgtm — all-in-one observability stack bundling an OTel Collector,
Tempo (traces), Prometheus (metrics), Loki (logs), and Grafana (UI) in a
single container. Receives all three OTLP signals.

| Setting | Value |
| --- | --- |
| Image | [`grafana/otel-lgtm:latest`](https://hub.docker.com/r/grafana/otel-lgtm) |
| Grafana UI | `3001` |
| OTLP gRPC receiver | `4317` |
| OTLP HTTP receiver | `4318` |
| Volume | `grafana-data` |
| Healthcheck | `wget -qO- http://localhost:3000/api/health` |

Enabled by setting `GIDEON_OTEL_ENABLED=true` and
`GIDEON_OTEL_EXPORTER=otlp` on the `fastapi` service. The Grafana UI is
available at `http://localhost:3001`. Pre-configured datasources for Tempo,
Prometheus, and Loki are available out of the box.

---

### minio

MinIO S3-compatible object store for original documents.

| Setting | Value |
| --- | --- |
| Image | [`minio/minio:latest`](https://hub.docker.com/r/minio/minio) |
| Internal API port | `9000` |
| Internal console port | `9001` |
| Volume | `minio-data` |
| Healthcheck | `mc ready local` |

Configured via `GIDEON_S3_*` environment variables (see
[SETTINGS.md](SETTINGS.md#s3settings-gideon_s3_-prefix)). The
`GIDEON_S3_ACCESS_KEY` and `GIDEON_S3_SECRET_KEY` values are mapped
to `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` in docker-compose so a
single `.env` entry drives both the application and the storage server.

The `minio-init` sidecar service creates the bucket automatically on first
run using `mc mb --ignore-existing`. FastAPI and celery-worker depend on
`minio-init` completing successfully before they start, guaranteeing the
bucket exists when the application boots.

---

### nextjs (disabled — profile: `frontend`)

Next.js frontend and reverse proxy. **Not yet implemented.** Enable with
`--profile frontend` when the frontend is ready.

| Setting | Value |
| --- | --- |
| Build context | `../frontend` |
| Public port | `3000` |
| Proxies to | `fastapi:8000` (internal) |
| Depends on | `fastapi` |

---

### ollama

Ollama local LLM and embedding server.

| Setting | Value |
| --- | --- |
| Image | [`ollama/ollama:latest`](https://hub.docker.com/r/ollama/ollama) |
| Internal port | `11434` |
| Volume | `ollama-models` |
| Healthcheck | `ollama list` |

Default LLM: `OLLAMA_LLM_MODEL` (default: `llama3.1:8b`).
Default embed model: `GIDEON_EMBEDDING_MODEL` (default: `nomic-embed-text`).

The `ollama-init` sidecar service pulls both the embedding model and the LLM
automatically on first run using `ollama pull`. FastAPI and celery-worker depend
on `ollama-init` completing successfully before they start, guaranteeing the
models are available when the application boots.

NVIDIA GPU acceleration is available — uncomment the `deploy.resources`
block in `docker-compose.yml` to enable it.

---

### ollama-init

One-shot init container that pulls the embedding model and LLM into Ollama.
Uses the `ollama/ollama:latest` image with `OLLAMA_HOST` pointed at the Ollama
server. Idempotent — pulling an already-present model is a no-op.

| Setting | Value |
| --- | --- |
| Image | [`ollama/ollama:latest`](https://hub.docker.com/r/ollama/ollama) |
| Depends on | `ollama` (healthy) |
| Restart | `no` |

Environment: `OLLAMA_HOST`, `EMBEDDING_MODEL`, `LLM_MODEL`.

---

### postgres

PostgreSQL 17 relational database.

| Setting | Value |
| --- | --- |
| Image | [`postgres:17-alpine`](https://hub.docker.com/_/postgres) |
| Public port | `${POSTGRES_PORT:-5432}:5432` |
| Volume | `postgres-data` |
| Init script | `infrastructure/postgres/init.sql` |
| Healthcheck | `pg_isready -U <user>` |

The init script runs once on first container startup and creates three
additional databases alongside the default `gideon` database:
`gideon_tasks` (Celery result backend), `gideon_test` (integration
tests), and `gideon_tasks_test` (integration test result backend).

---

### qdrant

Qdrant vector store (single collection, permission-filtered on every query).

| Setting | Value |
| --- | --- |
| Image | [`qdrant/qdrant:latest`](https://hub.docker.com/r/qdrant/qdrant) |
| Internal REST port | `6333` |
| Internal gRPC port | `6334` |
| Volume | `qdrant-data` |
| Healthcheck | `bash -c 'echo > /dev/tcp/localhost/6333'` |

Only accessible from within the Docker network. Collection name is
controlled by `GIDEON_QDRANT_COLLECTION` (default: `gideon`).

The `qdrant-init` sidecar service creates the collection automatically on first
run via the Qdrant REST API. FastAPI and celery-worker depend on `qdrant-init`
completing successfully before they start, guaranteeing the collection exists
when the application boots.

---

### qdrant-init

One-shot init container that creates the default Qdrant collection if it does
not exist. Uses `curlimages/curl:latest`. Idempotent — checks for collection
existence before creating.

| Setting | Value |
| --- | --- |
| Image | [`curlimages/curl:latest`](https://hub.docker.com/r/curlimages/curl) |
| Depends on | `qdrant` (healthy) |
| Restart | `no` |

Environment: `QDRANT_HOST`, `QDRANT_PORT`, `COLLECTION_NAME`,
`EMBEDDING_DIMENSIONS`.

---

### redis

Redis 7 task queue broker and cache.

| Setting | Value |
| --- | --- |
| Image | [`redis:7-alpine`](https://hub.docker.com/_/redis) |
| Internal port | `6379` |
| Volume | `redis-data` |
| Healthcheck | `redis-cli ping` |

Used as the Celery broker. Not exposed outside the Docker network.

---

## Volumes

| Volume | Service | Contents |
| --- | --- | --- |
| `postgres-data` | postgres | PostgreSQL data directory |
| `qdrant-data` | qdrant | Qdrant vector index and storage |
| `redis-data` | redis | Redis AOF persistence |
| `ollama-models` | ollama | Downloaded LLM and embedding models — **external volume** (`gideon-ollama-models`), preserved across `down -v` |
| `minio-data` | minio | Object store buckets and objects |
| `celery-tmp` | celery-worker | Ephemeral temp files during ingestion |
| `grafana-data` | grafana | Grafana dashboards, Tempo traces, Prometheus metrics, Loki logs |

All volumes are named (managed by Docker). Deleting volumes wipes the
corresponding data permanently.

---

## Port Map

| Port | Service | Access |
| --- | --- | --- |
| `3000` | Next.js | Disabled (profile: `frontend`) |
| `3001` | Grafana UI | Dev/test only — traces, metrics, logs |
| `4317` | Grafana OTLP gRPC | Internal (Docker network) |
| `4318` | Grafana OTLP HTTP | Internal (Docker network) |
| `5432` | PostgreSQL | Dev/test only |
| `5555` | Flower | Dev/test only — Celery monitoring UI |
| `8000` | FastAPI | Dev/test only — remove in production |
| `9000` | MinIO API | Dev/test only |
| `9001` | MinIO Console | Dev/test only |

Qdrant, Ollama, Redis, and Celery are internal only and not mapped to
host ports.

---

## Seeding the Database

### Admin Seed (automatic)

The FastAPI lifespan hook automatically seeds an admin user on startup
when `GIDEON_ADMIN_EMAIL` and `GIDEON_ADMIN_PASSWORD` are set.
See [SETTINGS.md](SETTINGS.md) for the full list of `GIDEON_ADMIN_*`
variables.

### Demo Seed (manual)

The `seed_demo` script populates the database with sample data for
development and testing via the API:

- **Virginia Cora** (attorney) — access to both matters
- **Jonathan Phillips** (paralegal) — access to Matter B only
- **People v. Smith** (Matter A)
- **People v. Jones** (Matter B)

```bash
# From the repo root (requires the stack to be running)
uv run python scripts/seed_demo.py
```

The script is idempotent — safe to run multiple times. Skips existing
records. Password for both demo users: `DemoPassword123!`

---

## Integration Test Stack

`infrastructure/docker-compose.integration.yml` is a Compose override used
automatically by `pytest-docker` (configured in `backend/tests/conftest.py`).

**Changes from base stack:**

- `fastapi` points at `gideon_test` database (created by `init.sql`)
- `fastapi` has OTel enabled (`EXPORTER=otlp`, targeting `grafana:4318`)
- `redis` exposes port `6379` to the host for test access
- `celery-worker` result backend points at `gideon_tasks_test`
- `minio` exposes ports `9000` and `9001` to the host for test access
- `flower` is disabled (not needed for tests)
- `nextjs` is disabled via profiles in the base compose file
- `qdrant` exposes port `6333` to the host for test access
- `qdrant-init` overrides collection name to `gideon_test`
- Active services: `postgres` + `redis` + `minio` + `qdrant` + `ollama` +
  `fastapi` + `celery-worker` + `celery-beat` + `grafana`

See the [Running the Stack](#running-the-stack) section above for how to
run integration tests.
