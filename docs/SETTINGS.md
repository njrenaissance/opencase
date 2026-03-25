# OpenCase — Settings Reference

All configuration is loaded by `backend/app/core/config.py` via
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).

**Load priority** (highest wins):

1. Environment variables
2. `.env` file
3. `config.json` file
4. Hard-coded defaults

Sub-settings classes use a dedicated env-var prefix shown below. Nested values are
accessed in Python as `settings.auth.secret_key`, `settings.db.url`, etc.

---

## Settings (`OPENCASE_` prefix)

Top-level application settings.

| Variable | Default | Description |
| --- | --- | --- |
| `OPENCASE_APP_NAME` | `OpenCase` | Application display name |
| `OPENCASE_DEBUG` | `false` | Enable FastAPI debug mode |
| `OPENCASE_LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `OPENCASE_LOG_OUTPUT` | `stdout` | Log stream: `stdout` or `stderr` |
| `OPENCASE_DEPLOYMENT_MODE` | `airgapped` | `airgapped` (manual upload only) or `internet` (enables cloud ingestion) |

---

## ApiSettings (`OPENCASE_API_` prefix)

HTTP server binding (uvicorn inside the container).

| Variable | Default | Description |
| --- | --- | --- |
| `OPENCASE_API_HOST` | `0.0.0.0` | Interface uvicorn binds to inside the container |
| `OPENCASE_API_PORT` | `8000` | Port uvicorn listens on inside the container |

FastAPI is never exposed on a public port. All external traffic routes through Next.js.

---

## AuthSettings (`OPENCASE_AUTH_` prefix)

JWT authentication, TOTP MFA, and account lockout policy.

| Variable | Default | Description |
| --- | --- | --- |
| `OPENCASE_AUTH_SECRET_KEY` | **required** | Signing key for JWT tokens. Generate: `openssl rand -base64 32` |
| `OPENCASE_AUTH_ALGORITHM` | `HS256` | JWT signing algorithm |
| `OPENCASE_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime in minutes |
| `OPENCASE_AUTH_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime in days |
| `OPENCASE_AUTH_TOTP_ISSUER` | `OpenCase` | Issuer label shown in authenticator apps |
| `OPENCASE_AUTH_TOTP_WINDOW` | `1` | Allowed TOTP time-step drift (± steps) |
| `OPENCASE_AUTH_BCRYPT_ROUNDS` | `12` | bcrypt work factor for password hashing |
| `OPENCASE_AUTH_LOGIN_LOCKOUT_ATTEMPTS` | `5` | Failed login attempts before account lockout |
| `OPENCASE_AUTH_LOGIN_LOCKOUT_MINUTES` | `15` | Lockout duration in minutes |

`OPENCASE_AUTH_SECRET_KEY` is required — the application will not
start without it.

---

## CelerySettings (`OPENCASE_CELERY_` prefix)

Celery task queue configuration.

| Variable | Default | Description |
| --- | --- | --- |
| `OPENCASE_CELERY_BROKER_URL` | `redis://redis:6379/0` | Message broker URL |
| `OPENCASE_CELERY_RESULT_BACKEND` | *none* | Task result backend DSN (see below) |
| `OPENCASE_CELERY_TASK_SERIALIZER` | `json` | Task serialization format |
| `OPENCASE_CELERY_ACCEPT_CONTENT` | `["json"]` | Accepted content types (JSON array) |
| `OPENCASE_CELERY_TIMEZONE` | `UTC` | Timezone for scheduled tasks |
| `OPENCASE_CELERY_WORKER_CONCURRENCY` | `2` | Concurrent worker processes |
| `OPENCASE_CELERY_TASK_SOFT_TIME_LIMIT` | `300` | Soft time limit per task (seconds) |
| `OPENCASE_CELERY_TASK_HARD_TIME_LIMIT` | `600` | Hard time limit per task (seconds) |
| `OPENCASE_CELERY_TASK_ACKS_LATE` | `true` | Acknowledge after completion (crash-safe) |
| `OPENCASE_CELERY_WORKER_PREFETCH_MULTIPLIER` | `1` | Tasks prefetched per worker (1 = fair) |

`OPENCASE_CELERY_RESULT_BACKEND` stores task results in the
`opencase_tasks` database on the shared Postgres instance. Uses the
synchronous `psycopg2` driver (not `asyncpg`):

```text
db+postgresql://user:pass@postgres:5432/opencase_tasks
```

Celery auto-creates the `celery_taskmeta` and `celery_tasksetmeta`
tables on first use — no Alembic migration needed.

---

## DbSettings (`OPENCASE_DB_` prefix)

PostgreSQL connection and connection-pool settings.

| Variable | Default | Description |
| --- | --- | --- |
| `OPENCASE_DB_URL` | **required** | SQLAlchemy async DSN, e.g. `postgresql+asyncpg://user:pass@host:5432/db` |
| `OPENCASE_DB_POOL_SIZE` | `10` | Number of persistent connections in the pool |
| `OPENCASE_DB_MAX_OVERFLOW` | `20` | Extra connections allowed beyond `POOL_SIZE` |
| `OPENCASE_DB_POOL_PRE_PING` | `true` | Validate connections before use (detects stale connections) |
| `OPENCASE_DB_ECHO` | `false` | Log all SQL statements — set `true` only for debugging |

`OPENCASE_DB_URL` is required — the application will not start without it.
In Docker Compose this value is assembled automatically from `POSTGRES_USER`,
`POSTGRES_PASSWORD`, and `POSTGRES_DB`; you do not set it directly in `.env`.

---

## FlowerSettings (`OPENCASE_FLOWER_` prefix)

Flower monitoring UI for Celery.

| Variable | Default | Description |
| --- | --- | --- |
| `OPENCASE_FLOWER_PORT` | `5555` | Flower web UI port |
| `OPENCASE_FLOWER_BASIC_AUTH` | *none* | Basic auth credentials (`user:password`, optional) |
| `OPENCASE_FLOWER_URL_PREFIX` | `/flower` | URL prefix for reverse proxy |

---

## OtelSettings (`OPENCASE_OTEL_` prefix)

OpenTelemetry observability — traces, metrics, and logs. All telemetry stays
on-premise.

| Variable | Default | Description |
| --- | --- | --- |
| `OPENCASE_OTEL_ENABLED` | `false` | Enable OpenTelemetry instrumentation |
| `OPENCASE_OTEL_EXPORTER` | `console` | Exporter backend: `console` (stdout) or `otlp` (Grafana otel-lgtm) |
| `OPENCASE_OTEL_ENDPOINT` | `http://localhost:4318` | OTLP HTTP endpoint (used when `EXPORTER=otlp`) |
| `OPENCASE_OTEL_SERVICE_NAME` | `opencase-api` | Service name tag on all spans, metrics, and logs |
| `OPENCASE_OTEL_SAMPLE_RATE` | `1.0` | Fraction of traces to sample (0.0–1.0) |

When `EXPORTER=otlp`, the Grafana UI is available at `http://localhost:3001`
with pre-configured datasources for Tempo (traces), Prometheus (metrics), and
Loki (logs).

---

## RedisSettings (`OPENCASE_REDIS_` prefix)

Redis connection settings. Individual fields are preferred over a monolithic URL
so each component is independently overridable. A computed `url` property
assembles them into a connection string at runtime.

| Variable | Default | Description |
| --- | --- | --- |
| `OPENCASE_REDIS_HOST` | `redis` | Redis host (Docker service name) |
| `OPENCASE_REDIS_PORT` | `6379` | Redis port |
| `OPENCASE_REDIS_DB` | `0` | Redis database number (0–15) |
| `OPENCASE_REDIS_PASSWORD` | *none* | Redis password (optional) |
| `OPENCASE_REDIS_SSL` | `false` | Enable TLS/SSL (`rediss://` scheme) |
| `OPENCASE_REDIS_POOL_SIZE` | `10` | Connection pool max connections |

The computed `url` property (e.g. `redis://redis:6379/0`) is available in
Python as `settings.redis.url` but is not set via an environment variable.
