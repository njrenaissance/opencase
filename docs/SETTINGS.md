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
| `OPENCASE_APP_VERSION` | *(package metadata)* | Read from installed package version |
| `OPENCASE_DEBUG` | `false` | Enable FastAPI debug mode |
| `OPENCASE_LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `OPENCASE_LOG_OUTPUT` | `stdout` | Log stream: `stdout` or `stderr` |
| `OPENCASE_DEPLOYMENT_MODE` | `airgapped` | `airgapped` (manual upload only) or `internet` (enables cloud ingestion) |

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

---

## ApiSettings (`OPENCASE_API_` prefix)

HTTP server binding (uvicorn inside the container).

| Variable | Default | Description |
| --- | --- | --- |
| `OPENCASE_API_HOST` | `0.0.0.0` | Interface uvicorn binds to inside the container |
| `OPENCASE_API_PORT` | `8000` | Port uvicorn listens on inside the container |

FastAPI is never exposed on a public port. All external traffic routes through Next.js.

---

## OtelSettings (`OPENCASE_OTEL_` prefix)

OpenTelemetry distributed tracing and metrics. All telemetry stays on-premise.

| Variable | Default | Description |
| --- | --- | --- |
| `OPENCASE_OTEL_ENABLED` | `false` | Enable OpenTelemetry instrumentation |
| `OPENCASE_OTEL_EXPORTER` | `console` | Exporter backend: `console` (stdout) or `otlp` (Jaeger / OTel Collector) |
| `OPENCASE_OTEL_ENDPOINT` | `http://localhost:4318` | OTLP HTTP endpoint (used when `EXPORTER=otlp`) |
| `OPENCASE_OTEL_SERVICE_NAME` | `opencase-api` | Service name tag on all spans and metrics |
| `OPENCASE_OTEL_SAMPLE_RATE` | `1.0` | Fraction of traces to sample (0.0–1.0) |

When `EXPORTER=otlp`, the Jaeger UI is available at `http://localhost:16686`
(default Docker Compose port). Jaeger does not ingest OTLP metrics —
metric export errors every 60 s are expected until an OTel Collector is added.
