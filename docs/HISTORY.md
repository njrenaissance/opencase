# OpenCase — Development Journal

A running log of the development process. Early entries are reconstructed
from the commit history. New entries are added by hand as work progresses.

---

## 2026-03-12 — Project kickoff and scaffolding

Started OpenCase from scratch. The goal: a free, self-hostable, AI-powered
discovery platform for solo and small criminal defense practitioners — built
first for Virginia Cora at Cora Firm in New York.

Spent the first session laying out the architecture and writing the initial
specs before touching any code. Wrote an architecture document with a Mermaid
service topology diagram, drafted a feature roadmap, and sketched out early
BDD scenarios for document ingestion. Added a MinIO S3 storage design and
started thinking through the permission model (firm isolation, matter scoping,
Jencks gating).

Then built the first real feature: a minimal FastAPI skeleton (`GET /health`,
`GET /ready`) with a clean package structure and `pyproject.toml` toolchain
(ruff, mypy strict, pytest-bdd). Immediately followed with a layered
configuration system using pydantic-settings — env vars, `.env` file, and
`config.json` all merged in priority order under an `OPENCASE_` prefix.

**Commits:** initial scaffold, MinIO design, architecture diagrams,
Feature 0.1 (FastAPI skeleton), Feature 0.2 (AppConfiguration)

---

## 2026-03-13 — Logging, observability, and containerization

Wired up Python's standard `logging` with configurable level and output
stream — kept it simple, no third-party log libraries. Then added
OpenTelemetry tracing and metrics with a console exporter as the initial
backend. Designed the OTel setup as a factory pattern: `setup_telemetry()`
takes settings and returns a `TracerProvider`, with lazy imports so the
console path never requires the OTLP package.

Built the backend Dockerfile using a two-stage build (builder + runtime) on
`python:3.12-slim`. Non-root user, no dev tools in the final image.

Spent some time restructuring the feature roadmap — expanded from 9 to 12
features as the scope of auth, RBAC, and the legal compliance requirements
became clearer.

**Commits:** Feature 0.3 (logging), Feature 0.4 (OTel), Feature 0.5
(Dockerfile), roadmap restructure

---

## 2026-03-14 — Roadmap refinement

Continued expanding the feature roadmap, adding detailed API routes, DB
model fields, and reordering features to reflect the correct build sequence
(scaffolding → API foundation → workers → storage → extraction → ingestion
→ audit → RBAC → chatbot → Brady tracker → witness index → legal hold).

**Commits:** roadmap expansion

---

## 2026-03-15 — Environment configuration

Created `.env.example` documenting every configurable environment variable
across all settings classes with sensible defaults. This becomes the
operator's first touchpoint when deploying.

**Commits:** Feature 0.6 (.env.example)

---

## 2026-03-16 — CI, database foundation, and a full integration stack

A dense day. Shipped six features.

**CI (Feature 0.7):** GitHub Actions workflows for format/lint (ruff),
unit tests, integration tests, AI code review, and container build. Added
a coverage gate — tests must maintain a minimum threshold to merge.

**Config expansion (Feature 1.1):** Added `AuthSettings` (JWT config, TOTP
settings, lockout policy) and `DbSettings` (async DSN, connection pool) as
nested pydantic-settings classes alongside the existing `OtelSettings`.
All required fields fail fast at startup with no default.

**Database foundation (Feature 1.2):** SQLAlchemy 2.0 async models for
`Firm`, `User`, `Matter`, and `MatterAssignment`. Alembic configured with
a single initial migration (`0001_initial_schema`). `User` carries the full
auth surface — bcrypt-hashed password, nullable encrypted TOTP secret,
lockout fields, role enum. `Matter` has legal hold and status fields from
day one. Wrote schema integration tests verifying the migration applies
cleanly against a real Postgres container.

**Docker Compose (Feature 0.8):** Full development stack with all planned
services — Next.js, FastAPI, PostgreSQL, Qdrant, Redis, MinIO, Ollama,
Celery worker, Celery beat. Added `ApiSettings`, switched integration tests
to `pytest-docker`, and introduced a compose override file for the test
stack.

**Observability (Feature 1.3):** Added module-level `logger.debug()` calls
to `session.py`, `health.py`, and `telemetry.py`. Created `metrics.py` with
four OTel auth metric instruments (`login_attempts`, `mfa_challenges`,
`token_refresh_attempts`, `active_sessions`) — wired up but not yet driven
(auth router comes in 1.4). Wired `SQLAlchemyInstrumentor` via a
`configure_instrumentation(app, settings)` factory function in `telemetry.py`
using a `TYPE_CHECKING` guard to avoid circular imports.

Had to work through a few non-obvious issues: `SQLAlchemyInstrumentor`
requires `engine.sync_engine` not the `AsyncEngine` directly, and logging
init order matters — `setup_logging()` must be called before other app
imports so module-level loggers respect `OPENCASE_LOG_LEVEL`.

Opened and merged PR #1.

**Commits:** Features 0.7, 1.1, 1.2, 0.8, 1.3, mypy fixes, PR #1 merge

---

## 2026-03-17 — Jaeger, integration tests, and documentation

**Jaeger (Feature 0.9):** Added Jaeger all-in-one as a Docker Compose
service (ports 16686 UI, 4317 gRPC, 4318 HTTP). Added an OTLP span exporter
factory alongside the existing console exporter. Added OTel env var
passthrough on the FastAPI service.

**Observability integration tests (1.3 follow-up):** Wrote `test_observability.py`
— plain pytest (not BDD, since this is infrastructure verification not
user-facing behavior). Tests poll Jaeger's REST API with a 10-second timeout
to verify that `GET /health` produces a FastAPI span and `GET /ready`
produces a SQLAlchemy `SELECT` span. The integration stack override enables
OTel with `EXPORTER=otlp` pointing at the Jaeger container.

Addressed several PR review issues across PRs #2, #3, and #4: logging init
order, port format in debug output, idempotent instrumentation, removing
`.claude/settings.local.json` from git tracking, Jaeger healthcheck, and
a startup warning for the known OTLP metrics 404 against Jaeger.

**Documentation:** Created `docs/SETTINGS.md` (full environment variable
reference for all five settings classes), `docs/INFRASTRUCTURE.md` (Docker
Compose services, ports, volumes, integration test stack), and updated
`docs/TOC.md` with a Reference section. Marked Features 1.1 and 1.2 docs
columns as Done in the roadmap. Fixed two accuracy issues found in code
review: removed `OPENCASE_APP_VERSION` (not user-settable), and added a
note that `OPENCASE_DB_URL` is assembled automatically by Docker Compose
from the `POSTGRES_*` vars.

**Commits:** Feature 0.9, 1.3 integration tests, PR review fixes (#2–#4),
SETTINGS.md, INFRASTRUCTURE.md, TOC updates

---

*Add new entries below as work continues.*
