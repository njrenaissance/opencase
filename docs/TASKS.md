# OpenCase — Background Tasks

OpenCase uses [Celery](https://docs.celeryq.dev/) for background task
processing. Tasks run in a separate worker process, decoupled from the
FastAPI request cycle, so long-running operations (document ingestion,
embedding, deadline monitoring) do not block API responses.

---

## Architecture

```text
FastAPI  ──TaskBroker.submit()──▶  Redis (broker)  ──▶  Celery Worker
  │                                                          │
  ▼                                                          ▼
PostgreSQL (main)                                       PostgreSQL
(task_submissions)                                   (opencase_tasks)
```

| Component | Role |
| --- | --- |
| **Redis** | Message broker — holds the task queue |
| **Celery Worker** | Picks tasks off the queue and executes them |
| **Celery Beat** | Submits scheduled tasks on a cron-based interval |
| **PostgreSQL (opencase_tasks)** | Stores task results via Celery's DB backend |

### How a task runs

1. API code calls `TaskBroker.submit()` — this serializes the call as
   JSON and pushes it onto a Redis queue. A `task_submissions` row is
   recorded in the main database for firm-scoped tracking.
2. The Celery worker pulls the message, deserializes it, and calls the
   Python function.
3. On completion (or failure), the result is written to the
   `opencase_tasks` database. The caller can poll the result by task ID.
4. The original API endpoint returns immediately with the task ID.
   The client polls `GET /tasks/{task_id}` to check progress.

### Celery Beat (scheduler)

Celery Beat is a **single** process that reads a schedule and submits
tasks at the configured intervals. It does not execute tasks — it only
enqueues them for the worker to pick up.

Beat stores its last-run timestamps in a local shelve file at
`/tmp/celery/celerybeat-schedule` (inside the `celery-tmp` volume). If
the file is lost (container recreated), Beat simply re-runs any overdue
tasks on next startup.

> **Important:** Never run more than one Beat instance. Multiple
> instances would submit duplicate tasks on every interval.

---

## Celery App

The Celery application is defined in
[`backend/app/workers/__init__.py`](../backend/app/workers/__init__.py).

```python
from app.workers import celery_app
```

Configuration is loaded from `settings.celery` (see
[SETTINGS.md](SETTINGS.md) for all `OPENCASE_CELERY_*` variables).
The app auto-discovers task modules in `app.workers.tasks`.

### Task discovery

Celery uses `autodiscover_tasks(["app.workers"])` which imports the
`app.workers.tasks` package. Task modules must be imported in
`backend/app/workers/tasks/__init__.py` so that their `@shared_task`
decorators run and register the tasks when the worker starts.

### `shared_task` vs `@celery_app.task`

Tasks use `@shared_task` (not `@celery_app.task`) to avoid circular
imports — task files do not need to import the Celery app instance.
`shared_task` registers the task in a global pending list that gets
bound to whichever app finalizes first.

---

## API Endpoints

Task management is exposed via REST endpoints on `/tasks/`. All
endpoints are firm-scoped — users only see tasks submitted by their
firm.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/tasks/` | Admin, Attorney | Submit a registered task |
| `GET` | `/tasks/` | Any authenticated | List tasks (filters: status, task_name, date range) |
| `GET` | `/tasks/{task_id}` | Any authenticated | Full detail + live Celery status |
| `PUT` | `/tasks/{task_id}` | Admin | Update (scaffold — no updatable fields yet) |
| `DELETE` | `/tasks/{task_id}` | Admin | Cancel a pending/running task |

`GET /tasks/{task_id}` enriches the response with live state from the
Celery result backend and denormalizes the status back to the
`task_submissions` table.

---

## TaskBroker

[`app/workers/broker.py`](../backend/app/workers/broker.py) provides a
thin abstraction over Celery so the API layer is decoupled from Celery
internals. This allows the background job backend to be swapped in the
future without touching the API router.

| Method | Signature | Purpose |
| --- | --- | --- |
| `submit` | `(celery_task_name, args, kwargs) → str` | Send task to broker, return task ID |
| `get_status` | `(task_id) → TaskStatusResult` | Query result backend for live state |
| `revoke` | `(task_id, *, terminate=False) → None` | Cancel a pending or running task |

`get_task_broker()` is the FastAPI dependency that returns the
singleton `TaskBroker` instance.

Each method emits an OTel span (`broker.submit`, `broker.get_status`,
`broker.revoke`) and records metrics (`opencase.tasks.submitted`,
`opencase.tasks.status_queried`, `opencase.tasks.cancelled`). See
[OBSERVABILITY.md](OBSERVABILITY.md) for the full span and metric tables.

---

## Task Registry (Whitelist)

[`app/workers/registry.py`](../backend/app/workers/registry.py)
defines `TASK_REGISTRY` — a dict mapping user-facing task names to
Celery task names. **Only tasks listed here can be submitted via the
API.** This is a security boundary: arbitrary Celery task names cannot
be invoked by API callers.

```python
TASK_REGISTRY: dict[str, str] = {
    "ping": "opencase.ping",
    "sleep": "opencase.sleep",
    "ingest_document": "opencase.ingest_document",
    "extract_document": "opencase.extract_document",
    "chunk_document": "opencase.chunk_document",
    "embed_chunks": "opencase.embed_chunks",
}
```

To make a new task submittable via the API, add an entry here in
addition to creating the task module (see "Adding a New Task" below).

---

## Registered Tasks

### `opencase.ping`

Health-check task for verifying worker connectivity.

| Field | Value |
| --- | --- |
| Module | `app.workers.tasks.ping` |
| Name | `opencase.ping` |
| Arguments | None |
| Returns | `"pong"` |
| Purpose | Integration test and health-check probe |

```python
from celery import Celery

app = Celery(broker="redis://redis:6379/0", backend="redis://redis:6379/1")
result = app.send_task("opencase.ping")
assert result.get(timeout=10) == "pong"
```

### `opencase.ingest_document`

Orchestrates the full document ingestion pipeline. Downloads the original
file from S3, extracts text via Apache Tika, persists `extracted.json`,
chunks the text, generates embeddings via Ollama, and upserts vectors to
Qdrant with permission metadata payload.

| Field | Value |
| --- | --- |
| Module | `app.workers.tasks.ingest_document` |
| Name | `opencase.ingest_document` |
| Arguments | `document_id: str`, `s3_key: str` |
| Returns | `{"status": "completed", "document_id": ..., "text_length": int, "chunk_count": int, "point_count": int}` |
| Purpose | Orchestrate ingestion: extraction → chunking → embedding → Qdrant upsert |

### `opencase.extract_document`

Extract text and metadata from a document stored in S3 using Apache
Tika. Returns the extraction result without persisting it — callers
(e.g. `ingest_document`) are responsible for storage.

| Field | Value |
| --- | --- |
| Module | `app.workers.tasks.extract_document` |
| Name | `opencase.extract_document` |
| Arguments | `document_id: str`, `s3_key: str` |
| Returns | `{"text": "...", "content_type": "...", "metadata": {...}, "ocr_applied": bool, "language": str\|null}` |
| Purpose | Download from S3, extract text via Tika, return `ExtractionResult` as dict |

### `opencase.chunk_document`

Split extracted document text into overlapping chunks with character
offsets. Uses the configured chunking strategy (default: recursive
character splitting via LangChain). Persists `chunks.json` to S3
alongside the original and extracted artifacts.

| Field | Value |
| --- | --- |
| Module | `app.workers.tasks.chunk_document` |
| Name | `opencase.chunk_document` |
| Arguments | `document_id: str`, `text: str`, `metadata: dict`, `s3_prefix: str` |
| Returns | `{"document_id": "...", "chunk_count": int, "chunks": [...]}` |
| Purpose | Split text into chunks, persist `chunks.json` to S3 |

### `opencase.embed_chunks`

Generate vector embeddings for document chunks using Ollama and upsert
the resulting vectors into Qdrant with full permission metadata payload.
Batches chunk texts according to `EmbeddingSettings.batch_size`, validates
returned vector dimensions, builds Qdrant points with deterministic IDs
(UUID5 from `document_id:chunk_index`), and batch-upserts to the
configured collection. Re-ingestion is idempotent — existing points are
overwritten.

| Field | Value |
| --- | --- |
| Module | `app.workers.tasks.embed_chunks` |
| Name | `opencase.embed_chunks` |
| Arguments | `document_id: str`, `chunks: list[dict]`, `payload_metadata: dict` |
| Returns | `{"document_id": "...", "chunk_count": int, "point_count": int}` |
| Purpose | Embed chunk texts via Ollama + upsert vectors to Qdrant with permission payload |

`payload_metadata` must contain at least: `firm_id`, `matter_id`,
`client_id`, `classification`, `source`. Optional: `bates_number`,
`page_number`. These fields are stored in every Qdrant point payload
to support `build_qdrant_filter()` RBAC enforcement.

### Future tasks

Tasks will be added as features are built:

| Task | Feature | Purpose |
| --- | --- | --- |
| Cloud ingestion | 6.7 | Poll SharePoint via Graph API |
| Deadline monitor | 10.10 | CPL 245 and 30.30 clock alerts (Beat-scheduled) |
| Audit chain validator | 7.3 | Nightly hash chain integrity check (Beat-scheduled) |

---

## Adding a New Task

1. Create a module in `backend/app/workers/tasks/`:

    ```python
    # backend/app/workers/tasks/my_task.py
    from celery import shared_task

    @shared_task(name="opencase.my_task")
    def my_task(arg1: str) -> dict:
        # ... do work ...
        return {"status": "done"}
    ```

2. Import the new module in `backend/app/workers/tasks/__init__.py`:

    ```python
    from app.workers.tasks.my_task import my_task  # noqa: F401
    ```

3. Use an explicit `name=` parameter. This decouples the task identity
   from the module path, so refactoring does not break in-flight tasks.

4. Add the task to `TASK_REGISTRY` in `app/workers/registry.py` so it
   can be submitted via the API:

    ```python
    TASK_REGISTRY: dict[str, str] = {
        "ping": "opencase.ping",
        "my_task": "opencase.my_task",
    }
    ```

5. Add unit tests in `backend/tests/test_workers.py` to verify the task
   is importable, registered, and returns the expected output when
   called directly.

---

## Result Backend

Task results are stored in a dedicated PostgreSQL database
(`opencase_tasks`) on the same Postgres instance as the main app
database. Celery's built-in SQLAlchemy backend auto-creates two tables:

| Table | Purpose |
| --- | --- |
| `celery_taskmeta` | Individual task results (task ID, status, result, traceback, date) |
| `celery_tasksetmeta` | Group/chord results |

The connection string uses the synchronous `psycopg2` driver (not
`asyncpg`) because Celery's result backend is synchronous:

```text
db+postgresql://user:pass@postgres:5432/opencase_tasks
```

---

## Docker Containers

All three containers share the same Docker image built from
`backend/docker/Dockerfile`. They differ only in the `command:` and
environment variables.

| Container | Command | Depends on |
| --- | --- | --- |
| `celery-worker` | `celery -A app.workers worker -l info` | postgres, redis, minio |
| `celery-beat` | `celery -A app.workers beat -l info --schedule /tmp/celery/celerybeat-schedule` | redis, postgres |
| `flower` | `celery -A app.workers flower --port=5555 --url_prefix=/flower` | redis |

All three containers set `SKIP_MIGRATIONS=true` — only the `db-migrate`
container and FastAPI run Alembic migrations.

Flower provides a web UI at `http://localhost:5555/flower` showing queue
depth, worker status, and task details. Basic auth is configurable via
`OPENCASE_FLOWER_BASIC_AUTH`.

See [INFRASTRUCTURE.md](INFRASTRUCTURE.md) for ports, volumes, and
health checks. See [SETTINGS.md](SETTINGS.md) for `OPENCASE_CELERY_*`
and `OPENCASE_REDIS_*` environment variables.

---

## Celery Configuration Reference

Key settings applied to the worker (all configurable via
`OPENCASE_CELERY_*` env vars):

| Setting | Default | Why |
| --- | --- | --- |
| `task_serializer` | `json` | No pickle — prevents arbitrary code execution |
| `accept_content` | `["json"]` | Reject non-JSON payloads |
| `task_acks_late` | `true` | Acknowledge after completion, not on receipt — safer crash recovery |
| `worker_prefetch_multiplier` | `1` | Fair scheduling — do not buffer extra tasks |
| `worker_concurrency` | `2` | Number of worker processes (tune to CPU cores) |
| `task_soft_time_limit` | `300` | Graceful timeout (5 min) — raises `SoftTimeLimitExceeded` |
| `task_time_limit` | `600` | Hard kill (10 min) — terminates the process |

---

## Further Reading

- [Celery documentation](https://docs.celeryq.dev/en/stable/)
- [Celery getting started](https://docs.celeryq.dev/en/stable/getting-started/first-steps-with-celery.html)
- [shared_task reference](https://docs.celeryq.dev/en/stable/reference/celery.html#celery.shared_task)
- [Task best practices](https://docs.celeryq.dev/en/stable/userguide/tasks.html#tips-and-best-practices)
- [Beat scheduler](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html)
- [Database result backend](https://docs.celeryq.dev/en/stable/userguide/configuration.html#database-backend-settings)
- [Monitoring with Flower](https://flower.readthedocs.io/en/latest/)
