# Gideon — Settings Reference

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

## Settings (`GIDEON_` prefix)

Top-level application settings.

| Variable | Default | Description |
| --- | --- | --- |
| `GIDEON_APP_NAME` | `Gideon` | Application display name |
| `GIDEON_DEBUG` | `false` | Enable FastAPI debug mode |
| `GIDEON_LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `GIDEON_LOG_OUTPUT` | `stdout` | Log stream: `stdout` or `stderr` |
| `GIDEON_DEPLOYMENT_MODE` | `airgapped` | `airgapped` (manual upload only) or `internet` (enables cloud ingestion) |

---

## ApiSettings (`GIDEON_API_` prefix)

HTTP server binding (uvicorn inside the container).

| Variable | Default | Description |
| --- | --- | --- |
| `GIDEON_API_HOST` | `0.0.0.0` | Interface uvicorn binds to inside the container |
| `GIDEON_API_PORT` | `8000` | Port uvicorn listens on inside the container |

FastAPI is never exposed on a public port. All external traffic routes through Next.js.

---

## AuthSettings (`GIDEON_AUTH_` prefix)

JWT authentication, TOTP MFA, and account lockout policy.

| Variable | Default | Description |
| --- | --- | --- |
| `GIDEON_AUTH_SECRET_KEY` | **required** | Signing key for JWT tokens. Generate: `openssl rand -base64 32` |
| `GIDEON_AUTH_ALGORITHM` | `HS256` | JWT signing algorithm |
| `GIDEON_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime in minutes |
| `GIDEON_AUTH_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime in days |
| `GIDEON_AUTH_TOTP_ISSUER` | `Gideon` | Issuer label shown in authenticator apps |
| `GIDEON_AUTH_TOTP_WINDOW` | `1` | Allowed TOTP time-step drift (± steps) |
| `GIDEON_AUTH_BCRYPT_ROUNDS` | `12` | bcrypt work factor for password hashing |
| `GIDEON_AUTH_LOGIN_LOCKOUT_ATTEMPTS` | `5` | Failed login attempts before account lockout |
| `GIDEON_AUTH_LOGIN_LOCKOUT_MINUTES` | `15` | Lockout duration in minutes |

`GIDEON_AUTH_SECRET_KEY` is required — the application will not
start without it.

---

## CelerySettings (`GIDEON_CELERY_` prefix)

Celery task queue configuration.

| Variable | Default | Description |
| --- | --- | --- |
| `GIDEON_CELERY_BROKER_URL` | `redis://redis:6379/0` | Message broker URL |
| `GIDEON_CELERY_RESULT_BACKEND` | *none* | Task result backend DSN (see below) |
| `GIDEON_CELERY_TASK_SERIALIZER` | `json` | Task serialization format |
| `GIDEON_CELERY_ACCEPT_CONTENT` | `["json"]` | Accepted content types (JSON array) |
| `GIDEON_CELERY_TIMEZONE` | `UTC` | Timezone for scheduled tasks |
| `GIDEON_CELERY_WORKER_CONCURRENCY` | `2` | Concurrent worker processes |
| `GIDEON_CELERY_TASK_SOFT_TIME_LIMIT` | `300` | Soft time limit per task (seconds) |
| `GIDEON_CELERY_TASK_HARD_TIME_LIMIT` | `600` | Hard time limit per task (seconds) |
| `GIDEON_CELERY_TASK_ACKS_LATE` | `true` | Acknowledge after completion (crash-safe) |
| `GIDEON_CELERY_WORKER_PREFETCH_MULTIPLIER` | `1` | Tasks prefetched per worker (1 = fair) |

`GIDEON_CELERY_RESULT_BACKEND` stores task results in the
`gideon_tasks` database on the shared Postgres instance. Uses the
synchronous `psycopg2` driver (not `asyncpg`):

```text
db+postgresql://user:pass@postgres:5432/gideon_tasks
```

Celery auto-creates the `celery_taskmeta` and `celery_tasksetmeta`
tables on first use — no Alembic migration needed.

---

## DbSettings (`GIDEON_DB_` prefix)

PostgreSQL connection and connection-pool settings.

| Variable | Default | Description |
| --- | --- | --- |
| `GIDEON_DB_URL` | **required** | SQLAlchemy async DSN, e.g. `postgresql+asyncpg://user:pass@host:5432/db` |
| `GIDEON_DB_POOL_SIZE` | `10` | Number of persistent connections in the pool |
| `GIDEON_DB_MAX_OVERFLOW` | `20` | Extra connections allowed beyond `POOL_SIZE` |
| `GIDEON_DB_POOL_PRE_PING` | `true` | Validate connections before use (detects stale connections) |
| `GIDEON_DB_ECHO` | `false` | Log all SQL statements — set `true` only for debugging |

`GIDEON_DB_URL` is required — the application will not start without it.
In Docker Compose this value is assembled automatically from `POSTGRES_USER`,
`POSTGRES_PASSWORD`, and `POSTGRES_DB`; you do not set it directly in `.env`.

---

## FlowerSettings (`GIDEON_FLOWER_` prefix)

Flower monitoring UI for Celery.

| Variable | Default | Description |
| --- | --- | --- |
| `GIDEON_FLOWER_PORT` | `5555` | Flower web UI port |
| `GIDEON_FLOWER_BASIC_AUTH` | *none* | Basic auth credentials (`user:password`, optional) |
| `GIDEON_FLOWER_URL_PREFIX` | `/flower` | URL prefix for reverse proxy |

---

## OtelSettings (`GIDEON_OTEL_` prefix)

OpenTelemetry observability — traces, metrics, and logs. All telemetry stays
on-premise.

| Variable | Default | Description |
| --- | --- | --- |
| `GIDEON_OTEL_ENABLED` | `false` | Enable OpenTelemetry instrumentation |
| `GIDEON_OTEL_EXPORTER` | `console` | Exporter backend: `console` (stdout) or `otlp` (Grafana otel-lgtm) |
| `GIDEON_OTEL_ENDPOINT` | `http://localhost:4318` | OTLP HTTP endpoint (used when `EXPORTER=otlp`) |
| `GIDEON_OTEL_SERVICE_NAME` | `gideon-api` | Service name tag on all spans, metrics, and logs |
| `GIDEON_OTEL_SAMPLE_RATE` | `1.0` | Fraction of traces to sample (0.0–1.0) |

When `EXPORTER=otlp`, the Grafana UI is available at `http://localhost:3001`
with pre-configured datasources for Tempo (traces), Prometheus (metrics), and
Loki (logs).

---

## S3Settings (`GIDEON_S3_` prefix)

S3-compatible object storage (MinIO). Individual fields are preferred over a
monolithic URL so each component is independently overridable. A computed `url`
property assembles the full endpoint URL at runtime.

| Variable | Default | Description |
| --- | --- | --- |
| `GIDEON_S3_ENDPOINT` | `minio:9000` | MinIO API endpoint (host:port) |
| `GIDEON_S3_ACCESS_KEY` | **required** | MinIO access key (also the root user) |
| `GIDEON_S3_SECRET_KEY` | **required** | MinIO secret key (also the root password) |
| `GIDEON_S3_BUCKET` | `gideon` | Default bucket for document storage |
| `GIDEON_S3_USE_SSL` | `false` | Use HTTPS for MinIO connections |
| `GIDEON_S3_REGION` | `us-east-1` | AWS region (MinIO default, required by boto3) |
| `GIDEON_S3_MAX_UPLOAD_BYTES` | `104857600` (100 MB) | Maximum file size for document uploads. The server rejects files exceeding this limit with HTTP 413. |
| `GIDEON_S3_SPOOL_THRESHOLD_BYTES` | `10485760` (10 MB) | In-memory buffer limit during upload hashing. Files smaller than this stay entirely in RAM; larger files spill to a temporary file on disk. Set this according to available server memory and expected file size distribution. |

`GIDEON_S3_ACCESS_KEY` and `GIDEON_S3_SECRET_KEY` are required — the
application will not start without them.

The computed `url` property (e.g. `http://minio:9000`) is available in Python
as `settings.s3.url` but is not set via an environment variable.

**Sizing guidance:** During document upload, the server buffers one file at a
time for SHA-256 hashing. Files below `SPOOL_THRESHOLD_BYTES` are hashed
in memory; larger files use a temporary file on disk. Ensure the temp
directory (`/tmp` by default) has at least `MAX_UPLOAD_BYTES` of free
space. For bulk ingestion workloads, the CLI uploads files sequentially
so only one file is in flight at a time.

---

## ExtractionSettings (`GIDEON_EXTRACTION_` prefix)

Document extraction pipeline — Apache Tika text extraction and Tesseract OCR.

| Variable | Default | Description |
| --- | --- | --- |
| `GIDEON_EXTRACTION_TIKA_URL` | `http://tika:9998` | Tika server endpoint |
| `GIDEON_EXTRACTION_OCR_ENABLED` | `true` | Enable Tesseract OCR for scanned documents |
| `GIDEON_EXTRACTION_OCR_LANGUAGES` | `eng` | Tesseract language packs (comma-separated, e.g. `eng,fra,deu`) |
| `GIDEON_EXTRACTION_REQUEST_TIMEOUT` | `120` | HTTP timeout for Tika requests (seconds) |
| `GIDEON_EXTRACTION_MAX_FILE_SIZE_BYTES` | `104857600` (100 MB) | Maximum file size sent to Tika for extraction |

---

## IngestionSettings (`GIDEON_INGESTION_` prefix)

Controls which document types are accepted for upload and CLI bulk-ingest.

| Variable | Default | Description |
| --- | --- | --- |
| `GIDEON_INGESTION_ALLOWED_TYPES_FILE` | *none* | Path to a flat file listing allowed MIME types and extensions |

When `ALLOWED_TYPES_FILE` is not set, built-in defaults are used. When set, the
file replaces the defaults entirely.

**File format:** one entry per line. Lines starting with `#` are comments. Blank
lines are ignored. MIME types (containing `/`) and file extensions (starting with
`.`) can be mixed freely:

```text
# Allowed MIME types
application/pdf
application/msword
text/plain

# Allowed file extensions (for CLI bulk-ingest discovery)
.pdf
.doc
.txt
```

**Default MIME types** (17): `application/pdf`, `application/msword`,
`application/vnd.openxmlformats-officedocument.wordprocessingml.document`,
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`,
`application/vnd.openxmlformats-officedocument.presentationml.presentation`,
`application/rtf`, `text/plain`, `text/markdown`, `text/csv`, `text/html`,
`image/jpeg`, `image/png`, `image/tiff`, `image/gif`, `image/bmp`,
`image/webp`, `application/octet-stream`.

**Default extensions** (19): `.pdf`, `.doc`, `.docx`, `.xlsx`, `.pptx`, `.rtf`,
`.txt`, `.md`, `.csv`, `.html`, `.htm`, `.jpg`, `.jpeg`, `.png`, `.tiff`,
`.tif`, `.gif`, `.bmp`, `.webp`.

The CLI fetches allowed types from the API at bulk-ingest start via
`GET /documents/ingestion-config`, so the server's configuration is always
the single source of truth.

---

## ChunkingSettings (`GIDEON_CHUNKING_` prefix)

Controls how extracted document text is split into overlapping chunks for
embedding and vector search.

| Variable | Default | Description |
| --- | --- | --- |
| `GIDEON_CHUNKING_STRATEGY` | `recursive` | Splitting strategy. Only `recursive` is supported. |
| `GIDEON_CHUNKING_CHUNK_SIZE` | `1000` | Maximum chunk size in characters |
| `GIDEON_CHUNKING_CHUNK_OVERLAP` | `200` | Overlap between consecutive chunks in characters |
| `GIDEON_CHUNKING_SEPARATORS` | `["\n\n", "\n", ". ", " ", ""]` | Ordered list of separators for recursive splitting |

`CHUNK_OVERLAP` must be strictly less than `CHUNK_SIZE`.

The `recursive` strategy uses LangChain's `RecursiveCharacterTextSplitter`.
It attempts to split on the first separator in the list; if a resulting
chunk exceeds `CHUNK_SIZE`, it recurses with the next separator. The empty
string `""` ensures every chunk fits within the limit. New strategies can be
added by implementing the `ChunkingStrategy` protocol and registering in
`STRATEGY_MAP`.

---

## RedisSettings (`GIDEON_REDIS_` prefix)

Redis connection settings. Individual fields are preferred over a monolithic URL
so each component is independently overridable. A computed `url` property
assembles them into a connection string at runtime.

| Variable | Default | Description |
| --- | --- | --- |
| `GIDEON_REDIS_HOST` | `redis` | Redis host (Docker service name) |
| `GIDEON_REDIS_PORT` | `6379` | Redis port |
| `GIDEON_REDIS_DB` | `0` | Redis database number (0–15) |
| `GIDEON_REDIS_PASSWORD` | *none* | Redis password (optional) |
| `GIDEON_REDIS_SSL` | `false` | Enable TLS/SSL (`rediss://` scheme) |
| `GIDEON_REDIS_POOL_SIZE` | `10` | Connection pool max connections |

The computed `url` property (e.g. `redis://redis:6379/0`) is available in
Python as `settings.redis.url` but is not set via an environment variable.
