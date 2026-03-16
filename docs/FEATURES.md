# OpenCase Feature Roadmap

## Feature 0 — Project Scaffolding

| ID | Feature | Status |
| --- | --- | --- |
| 0.1 | FastAPI skeleton (health endpoint, package structure) | Done |
| 0.2 | AppConfiguration (JSON + env via pydantic-settings) | Done |
| 0.3 | Logging (Python logging, level from AppConfiguration) | Done |
| 0.4 | Observability (OpenTelemetry traces/spans, metrics) | Done |
| 0.5 | Backend Dockerfile (run app for integration testing) | Done |
| 0.6 | `.env.example` | Done |
| 0.7a | CI: `format-lint.yml` (ruff) | Done |
| 0.7b | CI: `unit-tests.yml` (pytest @unit) | Done |
| 0.7c | CI: `integration-tests.yml` (pytest @integration) | Deferred |
| 0.7d | CI: `ai-code-review.yml` (same as Signatrust_v4) | Done |
| 0.7e | CI: `build-container.yml` (on spec/code change) | Done |
| 0.8 | Docker Compose — PostgreSQL service (volume, healthcheck, local dev + integration test target) | Done |

## Feature 1 — API

| ID | Feature | Specs | Code | Docs |
| --- | --- | --- | --- | --- |
| 1.1 | Configuration + env vars (ApiSettings, AuthSettings, DbSettings) | Done | Done | Pending |
| 1.2 | Database foundation (User, Firm, Matter models + Alembic) | Done | Done | Pending |
| 1.3 | Observability (auth spans/metrics, DB tracing) | Pending | Pending | Pending |
| 1.4 | Authentication (JWT, TOTP MFA, login/logout/refresh) | Pending | Pending | Pending |
| 1.5 | RBAC middleware (role enforcement, `build_qdrant_filter()`) | Pending | Pending | Pending |
| 1.6 | Python REST client SDK (backend/sdk/) | Pending | Pending | Pending |
| 1.7 | CLI (built on SDK) | Pending | Pending | Pending |
| 1.8 | Core business endpoints (matters, prompt stub, documents stub) | Pending | Pending | Pending |

## Feature 2 — Worker Queue

| ID | Feature | Specs | Code | Docs |
| --- | --- | --- | --- | --- |
| 2.1 | Redis broker container | Pending | Pending | Pending |
| 2.2 | Celery app + task definitions (app/workers/) | Pending | Pending | Pending |
| 2.3 | Celery worker container + Dockerfile | Pending | Pending | Pending |
| 2.4 | Celery Beat scheduler container | Pending | Pending | Pending |
| 2.5 | API integration (Celery client, task.delay() submission) | Pending | Pending | Pending |
| 2.6 | Task status API endpoint (read-only — query task progress/result by task ID for API-triggered tasks) | Pending | Pending | Pending |
| 2.7 | Observability (Flower container + OTel Celery instrumentation) | Pending | Pending | Pending |
| 2.8 | Task result persistence (separate Postgres instance, task lifecycle table for audit) | Pending | Pending | Pending |
| 2.9 | Configuration + env vars (CelerySettings, RedisSettings, FlowerSettings) | Pending | Pending | Pending |

## Feature 3 — S3 Storage

| ID | Feature | Specs | Code | Docs |
| --- | --- | --- | --- | --- |
| 3.1 | MinIO container setup + default bucket | Pending | Pending | Pending |
| 3.2 | API integration (boto3/minio-py, app/storage/) | Pending | Pending | Pending |
| 3.3 | Configuration + env vars (S3Settings) | Pending | Pending | Pending |
| 3.4 | Observability (S3 operation spans/metrics) | Pending | Pending | Pending |

## Feature 4 — Document Extraction

| ID | Feature | Specs | Code | Docs |
| --- | --- | --- | --- | --- |
| 4.1 | Tika container setup | Pending | Pending | Pending |
| 4.2 | Extraction task definitions (Celery tasks in app/workers/tasks/) | Pending | Pending | Pending |
| 4.3 | Configuration + env vars (ExtractionSettings) | Pending | Pending | Pending |
| 4.4 | Observability (extraction spans/metrics) | Pending | Pending | Pending |

## Feature 5 — Chunking & Embedding

| ID | Feature | Specs | Code | Docs |
| --- | --- | --- | --- | --- |
| 5.1 | Infrastructure setup (Qdrant collection, Ollama model pull, health checks) | Pending | Pending | Pending |
| 5.2 | Chunking task (Celery task, text splitting, overlap strategy) | Pending | Pending | Pending |
| 5.3 | Embedding task (Celery task, Ollama nomic-embed-text) | Pending | Pending | Pending |
| 5.4 | Qdrant upsert task (Celery task, vector storage, permission metadata payload) | Pending | Pending | Pending |
| 5.5 | Configuration + env vars (ChunkingSettings, QdrantSettings, OllamaSettings) | Pending | Pending | Pending |
| 5.6 | Observability (chunking/embedding spans/metrics) | Pending | Pending | Pending |

## Feature 6 — Document Ingestion

| ID | Feature | Specs | Code | Docs |
| --- | --- | --- | --- | --- |
| 6.1 | DB models + migration (documents table — metadata, SHA-256 hash, matter association, MinIO path, ingestion status; seed global knowledge matter) | Pending | Pending | Pending |
| 6.2 | Global knowledge matter (well-known system matter_id for CPL, case law, court rules — accessible to all users) | Pending | Pending | Pending |
| 6.3 | Manual upload Celery task (SHA-256 dedup, legal hold, store to MinIO, trigger extraction) | Pending | Pending | Pending |
| 6.4 | Manual upload API endpoint (receive file, call task.delay()) | Pending | Pending | Pending |
| 6.5 | Bulk upload API endpoint (multi-file, fan-out to individual tasks) | Pending | Pending | Pending |
| 6.6 | Document listing/status API endpoint (read-only — query documents by matter, ingestion status, metadata) | Pending | Pending | Pending |
| 6.7 | Cloud ingestion Celery task (OneDrive/SharePoint via Graph API) | Pending | Pending | Pending |
| 6.8 | Cloud ingestion Beat schedule (15-min polling interval) | Pending | Pending | Pending |
| 6.9 | Configuration + env vars (IngestionSettings) | Pending | Pending | Pending |
| 6.10 | Observability (ingestion spans/metrics) | Pending | Pending | Pending |

## Feature 7 — Audit Logging

| ID | Feature | Specs | Code | Docs |
| --- | --- | --- | --- | --- |
| 7.1 | DB models + migration (audit_log table — hash-chained entries) | Pending | Pending | Pending |
| 7.2 | Hash-chained log | Pending | Pending | Pending |
| 7.3 | Nightly chain validation | Pending | Pending | Pending |
| 7.4 | Audit log API endpoints (read-only — query, filter by event type/date/user/matter, export as PDF/CSV) | Pending | Pending | Pending |
| 7.5 | Configuration + env vars (AuditSettings — retention period, chain validation schedule, export formats) | Pending | Pending | Pending |

## Feature 8 — RBAC & MFA

| ID | Feature | Specs | Code | Docs |
| --- | --- | --- | --- | --- |
| 8.1 | DB models + migration (roles, user-role mapping, matter-user assignments, permissions) | Pending | Pending | Pending |
| 8.2 | Auth API endpoints (login, logout, refresh, MFA setup/verify) | Pending | Pending | Pending |
| 8.3 | JWT authentication | Pending | Pending | Pending |
| 8.4 | MFA (TOTP) | Pending | Pending | Pending |
| 8.5 | User management API endpoints (CRUD users, assign roles) | Pending | Pending | Pending |
| 8.6 | Four roles (Admin, Attorney, Paralegal, Investigator) | Pending | Pending | Pending |
| 8.7 | Matter assignment API endpoints (assign/revoke user-matter access) | Pending | Pending | Pending |
| 8.8 | Work product visibility | Pending | Pending | Pending |
| 8.9 | Session management (httpOnly cookies) | Pending | Pending | Pending |
| 8.10 | Auth audit trail (role changes, permission grants, matter assignment changes → audit log) | Pending | Pending | Pending |
| 8.11 | Observability (login/logout, failed attempts, MFA challenges, session metrics) | Pending | Pending | Pending |
| 8.12 | Configuration + env vars (AuthSettings — token expiry, refresh TTL, MFA window, lockout policy) | Pending | Pending | Pending |

## Feature 9 — Chatbot / Q&A

| ID | Feature | Specs | Code | Docs |
| --- | --- | --- | --- | --- |
| 9.1 | DB models + migration (chat_queries, conversation_history, feedback tables) | Pending | Pending | Pending |
| 9.2 | LLM inference model setup (Ollama model pull — Llama 3 8B / Mistral 7B, health check) | Pending | Pending | Pending |
| 9.3 | Matter-scoped RAG query API endpoint (LangChain + Qdrant retrieval + Ollama inference, wired up via FastAPI) | Pending | Pending | Pending |
| 9.4 | Minimal chat interface (CLI command or lightweight web UI for testing/demo) | Pending | Pending | Pending |
| 9.5 | Citation assembly | Pending | Pending | Pending |
| 9.6 | AI disclaimer | Pending | Pending | Pending |
| 9.7 | Conversation history | Pending | Pending | Pending |
| 9.8 | Audit logging of queries (metadata + reference ID → audit log, full query/response → chat_queries table) | Pending | Pending | Pending |
| 9.9 | User feedback API endpoints (submit: thumbs up/down, flag bad citations; query: filter by matter/date for analysis) | Pending | Pending | Pending |
| 9.10 | Configuration + env vars (ChatbotSettings — system prompt, model selection, temperature, max tokens, chunk retrieval count) | Pending | Pending | Pending |
| 9.11 | Observability (RAG query times, LLM response times, failed queries) | Pending | Pending | Pending |

## Feature 10 — Brady/Giglio Tracker

| ID | Feature | Specs | Code | Docs |
| --- | --- | --- | --- | --- |
| 10.1 | DB models + migration (disclosure_checklist, cpl_3030_events, motions, coc_tracking tables) | Pending | Pending | Pending |
| 10.2 | Tracker API endpoints (read-only — clocks, checklist, CoC status, motions, 30.30 events) | Pending | Pending | Pending |
| 10.3 | CPL 245 disclosure clocks | Pending | Pending | Pending |
| 10.4 | CPL 245.20(1) disclosure checklist (category tracking — what's received, what's outstanding) | Pending | Pending | Pending |
| 10.5 | Certificate of Compliance tracking (prosecution certification, defense challenges) | Pending | Pending | Pending |
| 10.6 | CPL 30.30 speedy trial clock (chargeable time, tolling events) | Pending | Pending | Pending |
| 10.7 | CPL 30.30 event ledger (dedicated table — every clock-affecting event with source document, chargeable party, running total) | Pending | Pending | Pending |
| 10.8 | Motion tracking (filed motions that affect clock tolling) | Pending | Pending | Pending |
| 10.9 | Brady/Giglio classification (AI-driven, updates disclosure checklist) | Pending | Pending | Pending |
| 10.10 | Deadline alerts (Celery Beat, approaching deadlines and overdue items) | Pending | Pending | Pending |
| 10.11 | Export API (CSV/JSON — disclosure checklist, clock status, classifications for case management import) | Pending | Pending | Pending |
| 10.12 | Configuration + env vars (TrackerSettings) | Pending | Pending | Pending |
| 10.13 | Observability (tracker spans/metrics) | Pending | Pending | Pending |

## Feature 11 — Witness Index

| ID | Feature | Specs | Code | Docs |
| --- | --- | --- | --- | --- |
| 11.1 | DB models + migration (witnesses, witness-document links, testimony status, aliases) | Pending | Pending | Pending |
| 11.2 | Witness API endpoints (read-only — list witnesses, view linked documents, testimony status) | Pending | Pending | Pending |
| 11.3 | Entity extraction Celery task (AI-driven name extraction from ingested documents) | Pending | Pending | Pending |
| 11.4 | Witness deduplication (resolve name variants — "Officer J. Smith" / "Det. Smith") | Pending | Pending | Pending |
| 11.5 | Witness-document linking | Pending | Pending | Pending |
| 11.6 | Giglio flagging (mark witnesses with impeachment material) | Pending | Pending | Pending |
| 11.7 | Jencks material gating (filter prior statements until has_testified = true) | Pending | Pending | Pending |
| 11.8 | Configuration + env vars (WitnessIndexSettings) | Pending | Pending | Pending |
| 11.9 | Observability (entity extraction spans/metrics) | Pending | Pending | Pending |

## Feature 12 — Legal Hold

| ID | Feature | Specs | Code | Docs |
| --- | --- | --- | --- | --- |
| 12.1 | Hold model (matter-level and document-level holds in PostgreSQL) | Pending | Pending | Pending |
| 12.2 | Hold API (create, release, query hold status) | Pending | Pending | Pending |
| 12.3 | Enforcement hooks (block delete/modify on held documents in S3 and DB) | Pending | Pending | Pending |
| 12.4 | Hold audit trail (all hold/release actions logged to audit chain) | Pending | Pending | Pending |
| 12.5 | Configuration + env vars (HoldSettings) | Pending | Pending | Pending |
| 12.6 | Observability (hold enforcement spans/metrics) | Pending | Pending | Pending |
