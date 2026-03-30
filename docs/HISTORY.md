# OpenCase — Development Journal

A running log of the development process. Early entries are reconstructed
from the commit history. New entries are added by hand as work progresses.

---

## 2026-03-12 — Project kickoff and scaffolding

*~3 hours (21:32–00:42)*

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

*~4.5 hours (11:51–16:11)*

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

*~1 hour (single evening session)*

Continued expanding the feature roadmap, adding detailed API routes, DB
model fields, and reordering features to reflect the correct build sequence
(scaffolding → API foundation → workers → storage → extraction → ingestion
→ audit → RBAC → chatbot → Brady tracker → witness index → legal hold).

**Commits:** roadmap expansion

---

## 2026-03-15 — Environment configuration

*~1 hour (single evening session)*

Created `.env.example` documenting every configurable environment variable
across all settings classes with sensible defaults. This becomes the
operator's first touchpoint when deploying.

**Commits:** Feature 0.6 (.env.example)

---

## 2026-03-16 — CI, database foundation, and a full integration stack

*~8 hours across three sessions (10:51–13:54, 18:08–21:32, 23:45–00:43)*

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

*~3 hours (00:03–00:43 late-night carryover, plus afternoon docs session)*

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

## 2026-03-17 — Authentication and RBAC

*~5 hours (branch created 13:28, commits 20:51–21:59 + Mar 18 00:30–00:41, 12:55–14:25)*

**Authentication (Feature 1.4):** Built the full auth flow — JWT access/refresh
tokens, TOTP-based MFA, login/logout/refresh endpoints. Added a `db-init`
service that runs Alembic migrations and seeds the admin user from env vars on
startup, so FastAPI doesn't boot until the schema is ready. Wrote an
authentication flow guide with Mermaid diagrams.

PR #8 review caught two issues: an unused `hash_password` re-export from the
auth router, and that `POST /auth/mfa/setup` would silently overwrite an
active TOTP secret. Added a guard so setup is rejected if MFA is already
enabled. Also hit a `python-jose` typing gap — `jwt.encode` returns `Any`,
which mypy strict rejects. Added `types-python-jose` to dev deps, then
discovered CI uses `uv sync --group dev` (reads `[dependency-groups]`, not
`[project.optional-dependencies]`), so had to add it in both places.

**RBAC (Feature 1.5):** Implemented the three core permission primitives:
`build_qdrant_filter()` (the most security-critical function — enforces firm
scoping, matter access, Jencks gating, and work product visibility on every
vector query), `require_role()` (FastAPI dependency factory for role-based
endpoint gating), and `require_matter_access()` (matter-level permission
check).

PR #10 review tightened the security model: extracted `_fetch_matter_access()`
with an explicit `Matter.firm_id == user.firm_id` join to prevent cross-firm
access even if a `MatterAccess` row were somehow miscreated across firms.
Also moved admin seed config from raw `os.environ` into validated Settings
fields.

**Commits:** Features 1.4, 1.5, db-init, auth docs, PR #8 and #10 fixes

---

## 2026-03-22 — SDK, shared models, and the Jaeger-to-Grafana pivot

*~3 hours (18:32–21:12)*

**Observability pivot:** Replaced Jaeger with `grafana/otel-lgtm` — a single
container that provides Tempo (traces), Prometheus (metrics), Loki (logs), and
Grafana (UI on port 3001). This was a significant improvement: instead of only
traces going to Jaeger, all three OTel signals now have backends. Added an
OTel log bridge so Python's standard `logging` flows to Loki with automatic
`trace_id`/`span_id` correlation. Had to fix the Grafana healthcheck —
the `otel-lgtm` image doesn't include `wget`, so switched to `curl`.

Also renamed `db-init` → `db-migrate` (the service only runs migrations now,
admin seeding moved to FastAPI lifespan), and made the admin seed reuse the
app's `AsyncSessionLocal` pool instead of creating a throwaway engine.

**SDK and shared models (Feature 1.6):** This was the biggest structural
change so far — splitting the codebase into three packages under a `uv`
workspace: `backend/` (FastAPI), `shared/` (Pydantic models and enums), and
`sdk/` (synchronous REST client). The shared package has minimal dependencies
(just pydantic) and is consumed by both backend and SDK. Rewired all backend
imports to use `shared.models.*` instead of local definitions.

The SDK includes auto-refresh (transparent token renewal), MFA flow support,
exception mapping, and `MockTransport`-based tests. PR #12 review caught a
thread safety issue in `AuthManager.refresh` — added a `threading.Lock` with
double-checked locking. Also fixed `logout()` to actually send the stored
refresh token for server-side revocation.

**Commits:** Jaeger→Grafana pivot, admin seed refactor, Feature 1.6,
PR #12 fixes, observability docs

---

## 2026-03-23 — Entity CRUD, demo seed, CLI, and worker queue config

*~6 hours across two sessions (10:47–11:36, 18:31–22:35)*

A marathon day — shipped five features and a pile of CI improvements.

**Entity CRUD:** Added read-only endpoints by default with full CRUD for
user/matter/matter-access management, all firm-scoped and RBAC-enforced
across three layers (shared models → API routers → SDK methods). 103 tests
across the three packages. Security: every query scopes to `firm_id`, sensitive
fields are excluded from responses, and access-denied returns 404 (not 403)
to avoid leaking resource existence.

**Demo seed:** Created a seed script with deterministic UUIDs (idempotent,
safe to rerun) populating Cora Firm with two users, two matters, and
differentiated access grants — Virginia (attorney) has access to both matters,
Jonathan (paralegal) only to one.

**CI hardening:** Added `mypy --strict` to pre-commit hooks, aligned
pre-commit with GitHub Actions across all three packages, and moved the
container build to on-demand only (no registry target yet).

**CLI (Feature 1.7):** Built the `opencase` command-line tool on Typer + Rich,
consuming the SDK for all API calls. Commands for health, auth, MFA, user/
matter/firm management, all with `--json` output for scripting. 61 tests, 87%
coverage. One subtle bug from code review: `logout` wasn't clearing local
tokens when the API call failed — moved cleanup into a `finally` block.

**Document and prompt stubs (Feature 1.8):** Added Document and Prompt
SQLAlchemy models, Alembic migration, stub endpoints, SDK methods, and CLI
commands. The Document model includes a SHA-256 `file_hash` with a
matter-scoped uniqueness constraint for deduplication from day one.

**Worker queue config (Feature 2.1):** Added `CelerySettings`,
`RedisSettings`, and `FlowerSettings` pydantic config classes. PR review caught
that special characters in Redis passwords break URLs — added `quote()` for
URL encoding. Also changed settings logging from INFO to DEBUG (no operator
needs to see connection strings on every boot) and made the redaction helper
smart enough to mask only the password component of URLs, not the whole value.

**Commits:** Entity CRUD (#14), demo seed, CI alignment, Feature 1.7,
Feature 1.8 (#16), Feature 2.1, multiple review fixes

---

## 2026-03-24 — Worker queue infrastructure

*~3 hours (evening session, commits 22:09–22:19 — bulk of work before first commit)*

**Redis + Celery containers (Features 2.1–2.4):** Wired up the complete
worker queue stack: Redis container with healthcheck, Celery worker and beat
containers sharing the backend Dockerfile, task autodiscovery via
`app.workers.tasks`, a `ping` health-check task, and a separate
`opencase_tasks` PostgreSQL database for Celery result persistence (fault
isolation from the main API database).

The Docker dependency chain required some thought — worker and beat must wait
for both postgres and redis to be healthy before starting. Integration tests
verify Redis connectivity, the readiness probe, and a full Celery task
round-trip (submit → execute → result).

Code review flagged several issues: guarding against `None` broker URL in
Celery app init, adding `socket_connect_timeout` to Redis healthcheck to
prevent DNS hangs, and properly closing Redis connections in test fixtures.

**Commits:** Features 2.1–2.4, review fixes

---

## 2026-03-25 — Task API, Flower monitoring, and MinIO storage

*~7 hours across three sessions (09:55–10:40, 15:25–16:02, 19:21–22:53)*

**Task CRUD API (Features 2.5–2.6):** Added `/tasks` router with submit, list,
get, and cancel endpoints. Tasks are submitted asynchronously to Celery via a
`TaskBroker` abstraction and tracked in a firm-scoped `task_submissions` table.
Includes a task whitelist registry, OTel instrumentation, and RBAC (admin/
attorney can submit, admin-only cancel). Added SDK methods and CLI commands.

One non-obvious issue: FastAPI needs `OPENCASE_CELERY_BROKER_URL` and
`OPENCASE_CELERY_RESULT_BACKEND` env vars to submit tasks and query results
via `TaskBroker`. Without them, the Celery client initialized with a
`DisabledBackend` and `get_status()` raised an `AttributeError`. Added a
`submit_task.py` script for manual testing and an `opencase.sleep` task for
observability testing in Flower and Grafana.

**Flower monitoring (Feature 2.7):** Deployed Flower for real-time queue
monitoring and wired `CeleryInstrumentor` into worker/beat processes. Code
review pushed for moving OTel init from import-time to Celery
`worker_init`/`beat_init` signals to avoid global state pollution during
tests. Also extracted Flower into an optional `[monitoring]` dependency and
added an `INSTALL_EXTRAS` build arg to the Dockerfile so worker/API/beat
images stay lean.

**S3 storage foundation (Feature 3.3):** Added `S3Settings` pydantic config,
renamed `MINIO_*` env vars to `OPENCASE_S3_*` for prefix consistency,
enabled MinIO in the integration test stack, and added a `minio-init` sidecar
container for automatic bucket creation. Integration tests verify readiness
probe, bucket existence, and object put/get round-trip.

One pain point: `Settings()` validates all required fields at import time,
even for services that don't use S3. Had to add `OPENCASE_S3_ACCESS_KEY` and
`OPENCASE_S3_SECRET_KEY` to every Docker Compose service, including ones like
`db-migrate` and `flower` that never touch S3.

**Commits:** Features 2.5–2.7, Feature 3.3, MinIO init (#28), multiple
review rounds

---

## 2026-03-27 — Document upload and S3 integration

*~3 hours (23:25–01:02, plus Mar 26 MinIO init 12:06–12:18)*

**S3 document upload (Feature 3.2):** Replaced the stub document endpoints
with a full multipart upload flow. Documents are SHA-256 hashed on upload
(100 MB size limit), stored in MinIO via `S3StorageService`, and deduplicated
within each matter. Added content-type allowlisting, filename sanitization,
and RFC 5987 `Content-Disposition` encoding to prevent header injection.

The upload flow includes S3 orphan cleanup on DB commit failure — if the
database insert fails after the file is already in S3, the orphaned object
is deleted. Code review caught that the cleanup `try/except` should preserve
the original exception if the S3 delete also fails, and that
`Content-Disposition` needs both an ASCII fallback (`filename=`) and a UTF-8
encoded form (`filename*=`) for older client compatibility.

Also stubbed out `IngestionService` and the `ingest_document` Celery task as
the entry point for the extraction pipeline.

**Commits:** Feature 3.2, docs updates, review fixes

---

## 2026-03-28 — CLI bulk ingest, extraction config, SDK refactor, and licensing

*~8 hours across four sessions (00:02–01:02, 10:43–10:55, 12:41–16:33, 18:07–21:52)*

**Bulk ingest CLI:** Added `opencase document bulk-ingest` — walks a local
directory, pre-hashes files client-side, checks for duplicates via a new
lightweight `GET /documents/check-duplicate` endpoint, and uploads
non-duplicates via multipart form data. Replaced in-memory `BytesIO` buffering
with `SpooledTemporaryFile` (configurable 10 MB threshold) so large uploads
spill to disk instead of consuming memory. Added configurable
`OPENCASE_S3_MAX_UPLOAD_BYTES` and `OPENCASE_S3_SPOOL_THRESHOLD_BYTES`
settings with a model validator ensuring spool threshold doesn't exceed max
upload size.

**Extraction and ingestion config:** Added `ExtractionSettings`
(OPENCASE_EXTRACTION_ prefix) for Tika/OCR pipeline configuration and
`IngestionSettings` (OPENCASE_INGESTION_ prefix) for configurable document
type allowlists. Allowed MIME types and file extensions are now loaded from
an optional flat file, replacing hardcoded constants. The CLI's `bulk-ingest`
fetches allowed extensions from the API at runtime so the server is the single
source of truth.

**SDK refactor:** Renamed `OpenCaseClient` → `Client` and introduced
`opencase.Session` — a context manager that automates the login/logout
lifecycle and scrubs credentials from memory after authentication. Code review
pushed credential scrubbing into a `finally` block so email/password are
cleared even when `login()` raises.

**Scope clarification:** Cleaned up all references to "OneDrive/SharePoint" —
cloud ingestion targets SharePoint document libraries only, not personal
OneDrive drives.

**Licensing:** Added Apache 2.0 LICENSE file and a third-party license
inventory (`LICENSING.md`) covering infrastructure services, Python
dependencies, LLM models, and planned components. The analysis confirmed
Apache 2.0 compatibility despite AGPL components (network services, not
linked) and LGPL components (dynamic linking only).

**Tika container:** Added Apache Tika 3.1.0.0 as a Docker Compose service
for document text extraction. Used a Perl-based HTTP healthcheck since Tika's
image doesn't include `curl` or `wget`. Had to add a `start_period` to the
healthcheck because Tika's JVM cold start takes 10–15 seconds before the HTTP
endpoint responds.

**Commits:** Bulk ingest, extraction/ingestion config (#40, #38), Client
rename (#37), SharePoint scope (#41), LICENSE (#39), Tika container, scripts
reorganization

---

## 2026-03-30 — Document extraction pipeline

*~3 hours (branch created Mar 28 22:58, commits 12:31–12:41)*

**TikaExtractionService and extract_document task (#48):** Wired up the
end-to-end document extraction pipeline. `TikaExtractionService` wraps
httpx for async HTTP calls to Tika, returning an `ExtractionResult` dataclass
with extracted text, metadata, page count, and content type. The
`extract_document` Celery task is registered in the task whitelist and the
`ingest_document` task was un-stubbed to orchestrate the full flow: S3
download → Tika extraction → persist `extracted.json` back to S3.

A few Tika 3.x compatibility lessons: content must be sent as
`application/octet-stream` (Tika auto-detects format), the OCR language
header isn't supported in the same way, and the `/rmeta/text` endpoint
returns both text and metadata in a single call (halving latency compared to
separate `/tika` and `/meta` calls).

One tricky issue: httpx clients can't be reused across Celery task invocations
because the event loop may be closed between calls. Switched to creating a
fresh httpx client per extraction call instead of using a shared instance.

Code review also tightened the S3 key parsing (using `rsplit` instead of
positional split to handle keys with multiple path separators) and widened
the Tika metadata type annotation to `dict[str, object]` since Tika returns
mixed types (strings, lists, numbers) in its metadata response.

**Commits:** TikaExtractionService (#48), review fixes

---

## Running Total

| Date | Est. Hours |
| --- | --- |
| Mar 12 | ~3 |
| Mar 13 | ~4.5 |
| Mar 14 | ~1 |
| Mar 15 | ~1 |
| Mar 16 | ~8 |
| Mar 17 | ~8 |
| Mar 22 | ~3 |
| Mar 23 | ~6 |
| Mar 24 | ~3 |
| Mar 25 | ~7 |
| Mar 27 | ~3 |
| Mar 28 | ~8 |
| Mar 30 | ~3 |
| **Total to date** | **~59 ± 7 hours** |

**Estimated remaining (critical path to MVP — Features 5–9):**

| Feature | Est. Hours | Notes |
| --- | --- | --- |
| 5 — Chunking & Embedding | ~15 | Qdrant, Ollama, text splitting |
| 6 — Ingestion (finish) | ~10 | Pipeline completion, skip cloud sync |
| 7 — Audit Logging | ~15 | Hash chain, validation, export |
| 8 — RBAC & MFA (fill gaps) | ~10 | Mostly built in 1.4/1.5 |
| 9 — Chatbot / Q&A | ~40–50 | RAG core — biggest unknown |
| **Remaining estimate** | **~90–100** | |
| **Projected total** | **~150–160 hours** | |

Deferred to V1.1: Brady/Giglio tracker (10), witness index (11),
legal hold (12), cloud ingestion (6.7/6.8), release engineering.
Target: MVP complete by mid-May 2026 (~6 weeks at 20–25 hrs/week).

Time estimates are derived from branch creation timestamps and commit
clustering. Each day carries ±0.5 hour margin (work before first commit
and between commits is not captured). Days with no commits (Mar 18, 19–21,
26, 29) had their work folded into adjacent entries.

---

*Add new entries below as work continues.*
