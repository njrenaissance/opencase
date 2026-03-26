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
| `infrastructure/postgres/init.sql` | Creates `opencase_tasks`, `opencase_test`, and `opencase_tasks_test` DBs on first startup |

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
At minimum, set `OPENCASE_AUTH_SECRET_KEY`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `OPENCASE_S3_ACCESS_KEY`, and
`OPENCASE_S3_SECRET_KEY`.

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
| Depends on | `postgres` (healthy), `redis` (healthy), `minio` (healthy) |

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
the FastAPI lifespan hook (see `OPENCASE_ADMIN_*` env vars in
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
| Depends on | `db-migrate` (completed), `redis` (healthy) |

The public port mapping (`8000:8000`) is present for local development and
integration tests. In production it should be removed — all external traffic
must route through Next.js.

On startup the lifespan hook seeds the initial admin user if
`OPENCASE_ADMIN_EMAIL` and `OPENCASE_ADMIN_PASSWORD` are set. The seed is
idempotent and reuses the app's existing database connection pool.

---

### flower

Flower — Celery monitoring web UI for real-time task and worker visibility.

| Setting | Value |
| --- | --- |
| Build context | `..` (repo root) |
| Dockerfile | `backend/docker/Dockerfile` |
| Command | `celery -A app.workers flower --port=5555 --url_prefix=/flower` |
| Public port | `${OPENCASE_FLOWER_PORT:-5555}:5555` |
| Depends on | `redis` (healthy) |

Provides a dashboard showing queue depth, worker status, active/completed
tasks, and task details. Basic auth is configurable via
`OPENCASE_FLOWER_BASIC_AUTH` (format: `user:password`). OTel is disabled
for Flower — it is a monitoring UI, not a task producer.

---

### grafana (otel-lgtm)

Grafana otel-lgtm — all-in-one observability stack bundling an OTel Collector,
Tempo (traces), Prometheus (metrics), Loki (logs), and Grafana (UI) in a
single container. Receives all three OTLP signals.

| Setting | Value |
| --- | --- |
| Image | `grafana/otel-lgtm:latest` |
| Grafana UI | `3001` |
| OTLP gRPC receiver | `4317` |
| OTLP HTTP receiver | `4318` |
| Volume | `grafana-data` |
| Healthcheck | `wget -qO- http://localhost:3000/api/health` |

Enabled by setting `OPENCASE_OTEL_ENABLED=true` and
`OPENCASE_OTEL_EXPORTER=otlp` on the `fastapi` service. The Grafana UI is
available at `http://localhost:3001`. Pre-configured datasources for Tempo,
Prometheus, and Loki are available out of the box.

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

Configured via `OPENCASE_S3_*` environment variables (see
[SETTINGS.md](SETTINGS.md#s3settings-opencase_s3_-prefix)). The
`OPENCASE_S3_ACCESS_KEY` and `OPENCASE_S3_SECRET_KEY` values are mapped
to `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` in docker-compose so a
single `.env` entry drives both the application and the storage server.

---

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

### postgres

PostgreSQL 17 relational database.

| Setting | Value |
| --- | --- |
| Image | `postgres:17-alpine` |
| Public port | `${POSTGRES_PORT:-5432}:5432` |
| Volume | `postgres-data` |
| Init script | `infrastructure/postgres/init.sql` |
| Healthcheck | `pg_isready -U <user>` |

The init script runs once on first container startup and creates three
additional databases alongside the default `opencase` database:
`opencase_tasks` (Celery result backend), `opencase_test` (integration
tests), and `opencase_tasks_test` (integration test result backend).

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

## Volumes

| Volume | Service | Contents |
| --- | --- | --- |
| `postgres-data` | postgres | PostgreSQL data directory |
| `qdrant-data` | qdrant | Qdrant vector index and storage |
| `redis-data` | redis | Redis AOF persistence |
| `ollama-models` | ollama | Downloaded LLM and embedding models |
| `minio-data` | minio | Object store buckets and objects |
| `celery-tmp` | celery-worker | Ephemeral temp files during ingestion |
| `grafana-data` | grafana | Grafana dashboards, Tempo traces, Prometheus metrics, Loki logs |

All volumes are named (managed by Docker). Deleting volumes wipes the
corresponding data permanently.

---

## Port Map

| Port | Service | Access |
| --- | --- | --- |
| `3000` | Next.js | Public — browser entry point |
| `3001` | Grafana UI | Dev/test only — traces, metrics, logs |
| `4317` | Grafana OTLP gRPC | Internal (Docker network) |
| `4318` | Grafana OTLP HTTP | Internal (Docker network) |
| `5432` | PostgreSQL | Dev/test only |
| `5555` | Flower | Dev/test only — Celery monitoring UI |
| `8000` | FastAPI | Dev/test only — remove in production |
| `9000` | MinIO API | Internal (Docker network) |
| `9001` | MinIO Console | Internal (Docker network) |

All other services (Qdrant, Redis, Ollama, Celery) are internal only
and not mapped to host ports.

---

## Seeding the Database

### Admin Seed (automatic)

The FastAPI lifespan hook automatically seeds an admin user on startup
when `OPENCASE_ADMIN_EMAIL` and `OPENCASE_ADMIN_PASSWORD` are set.
See [SETTINGS.md](SETTINGS.md) for the full list of `OPENCASE_ADMIN_*`
variables.

### Demo Seed (manual)

The `seed_demo` script populates the database with sample data for
development and testing:

- **Cora Firm**
- **Virginia Cora** (attorney) — access to both matters
- **Jonathan Phillips** (paralegal) — access to Matter B only
- **People v. Smith** (Matter A)
- **People v. Jones** (Matter B)

```bash
# From the backend directory (requires the stack to be running)
cd backend
uv run python -m scripts.seed_demo
```

The script is idempotent — safe to run multiple times. It uses
deterministic UUIDs so re-runs skip existing records. Password for
both demo users: `DemoPassword123!`

---

## Integration Test Stack

`infrastructure/docker-compose.integration.yml` is a Compose override used
automatically by `pytest-docker` (configured in `backend/tests/conftest.py`).

**Changes from base stack:**

- `fastapi` points at `opencase_test` database (created by `init.sql`)
- `fastapi` has OTel enabled (`EXPORTER=otlp`, targeting `grafana:4318`)
- `redis` exposes port `6379` to the host for test access
- `celery-worker` result backend points at `opencase_tasks_test`
- `minio` exposes ports `9000` and `9001` to the host for test access
- All unneeded services are disabled via Docker Compose profiles:
  `nextjs`, `ollama`, `qdrant`, `flower`
- Active services: `postgres` + `redis` + `minio` + `fastapi` +
  `celery-worker` + `celery-beat` + `grafana`

To run integration tests:

```bash
cd backend
uv run pytest -m integration
```

pytest-docker starts the stack before tests and tears it down with `-v`
afterward so the test database is wiped between runs.
