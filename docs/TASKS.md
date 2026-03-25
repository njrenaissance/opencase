# OpenCase — Background Tasks

OpenCase uses [Celery](https://docs.celeryq.dev/) for background task
processing. Tasks run in a separate worker process, decoupled from the
FastAPI request cycle, so long-running operations (document ingestion,
embedding, deadline monitoring) do not block API responses.

---

## Architecture

```text
FastAPI  ──task.delay()──▶  Redis (broker)  ──▶  Celery Worker
                                                      │
                                                      ▼
                                                 PostgreSQL
                                              (opencase_tasks)
```

| Component | Role |
| --- | --- |
| **Redis** | Message broker — holds the task queue |
| **Celery Worker** | Picks tasks off the queue and executes them |
| **Celery Beat** | Submits scheduled tasks on a cron-based interval |
| **PostgreSQL (opencase_tasks)** | Stores task results via Celery's DB backend |

### How a task runs

1. API code calls `task_name.delay(args)` — this serializes the call as
   JSON and pushes it onto a Redis queue.
2. The Celery worker pulls the message, deserializes it, and calls the
   Python function.
3. On completion (or failure), the result is written to the
   `opencase_tasks` database. The caller can poll the result by task ID.
4. The original API endpoint can return immediately with the task ID,
   then the client polls a status endpoint (Feature 2.6).

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

## Task Registry

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

### Future tasks

Tasks will be added as features are built:

| Task | Feature | Purpose |
| --- | --- | --- |
| Document ingestion | 6.3 | SHA-256 dedup, store to MinIO, trigger extraction |
| Cloud ingestion | 6.7 | Poll OneDrive/SharePoint via Graph API |
| Text extraction | 4.2 | Parse documents via Apache Tika |
| Chunking + embedding | 5.2, 5.3 | Split text, embed via Ollama, upsert to Qdrant |
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

4. Call from the API:

    ```python
    from app.workers.tasks.my_task import my_task

    result = my_task.delay("some_arg")
    # result.id is the task ID for status polling
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

Both containers set `SKIP_MIGRATIONS=true` — only the `db-migrate`
container and FastAPI run Alembic migrations.

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
