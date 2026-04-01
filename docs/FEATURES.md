# OpenCase Feature Roadmap

| ID | Feature | Status |
| --- | --- | --- |
| **0.0** | **Project Scaffolding** | **Done** |
| 0.1 | FastAPI skeleton (health endpoint, package structure) | Done |
| 0.2 | AppConfiguration (JSON + env via pydantic-settings) | Done |
| 0.3 | Logging (Python logging, level from AppConfiguration) | Done |
| 0.4 | Observability (OpenTelemetry traces/spans, metrics) | Done |
| 0.5 | Backend Dockerfile (run app for integration testing) | Done |
| 0.6 | `.env.example` | Done |
| 0.7 | CI: GitHub Actions (format/lint, unit tests, integration tests, AI code review, container build) | Done |
| 0.8 | Docker Compose — PostgreSQL service (volume, healthcheck, local dev + integration test target) | Done |
| 0.9 | Grafana otel-lgtm — unified observability (traces, metrics, logs via OTLP, Grafana UI) | Done |
| **1.0** | **API** | **Done** |
| 1.1 | Configuration + env vars (ApiSettings, AuthSettings, DbSettings) | Done |
| 1.2 | Database foundation (User, Firm, Matter models + Alembic) | Done |
| 1.3 | Observability (auth spans/metrics, DB tracing) | Done |
| 1.4 | Authentication (JWT, TOTP MFA, login/logout/refresh) | Done |
| 1.5 | RBAC middleware (role enforcement, `build_qdrant_filter()`) | Done |
| 1.6 | Python REST client SDK + shared models (sdk/, shared/) | Done |
| 1.8 | Core business endpoints (matters, prompt stub, documents stub) | Done |
| 1.7 | CLI (built on SDK) | Done |
| 1.6.1 | SDK: rename `OpenCaseClient` → `Client` (backwards-compat alias kept) | Done |
| 1.6.2 | SDK: `Session` context manager — auto login/logout, credential scrubbing | Done |
| **2.0** | **Worker Queue** | **Done** |
| 2.1 | Configuration + env vars (CelerySettings, RedisSettings, FlowerSettings) | Done |
| 2.2 | Redis broker + Celery worker + Beat containers (Dockerfile, health checks, env wiring) | Done |
| 2.3 | Celery app + task definitions (app/workers/) | Done |
| 2.4 | Task result persistence (opencase_tasks DB on shared Postgres, Celery DB backend) | Done |
| 2.5 | API integration (Celery client, task.delay() submission) | Done |
| 2.6 | Task status API endpoint (read-only — query task progress/result by task ID for API-triggered tasks) | Done |
| 2.7 | Observability (Flower container + OTel Celery instrumentation) | Done |
| **3.0** | **S3 Storage** | **Done** |
| 3.1 | MinIO container setup + default bucket | Done |
| 3.3 | Configuration + env vars (S3Settings) | Done |
| 3.2 | API integration (boto3/minio-py, app/storage/) | Done |
| 3.4 | Observability (S3 operation spans/metrics) | Done |
| **4.0** | **Document Extraction** | **Done** |
| 4.1 | Tika container setup | Done |
| 4.3 | Configuration + env vars (ExtractionSettings) | Done |
| 4.2 | Extraction task definitions (Celery tasks in app/workers/tasks/) | Done |
| 4.4 | Observability (extraction spans/metrics) | Done |
| **5.0** | **Chunking & Embedding** | **Done** |
| 5.5 | Configuration + env vars (ChunkingSettings, EmbeddingSettings, QdrantSettings) | Done |
| 5.1 | Infrastructure setup (Qdrant collection, Ollama model pull, health checks) | Done |
| 5.2 | Chunking task (Celery task, text splitting, overlap strategy) | Done |
| 5.3 | Embedding task (Celery task, Ollama nomic-embed-text) | Done |
| 5.4 | Qdrant upsert task (Celery task, vector storage, permission metadata payload) | Done |
| 5.6 | Observability (chunking/embedding spans/metrics) | Done |
| **6.0** | **Document Ingestion** | **Pending** |
| 6.4 | Manual upload API endpoint (receive file via multipart form, SHA-256 hash + dedup, S3 upload, fire-and-forget ingestion) | Done |
| 6.11 | Duplicate-check API endpoint (`GET /documents/check-duplicate` — lightweight pre-upload hash check) | Done |
| 6.12 | Disk-buffered hashing (SpooledTemporaryFile — small files in RAM, large files spill to disk) | Done |
| 6.13 | SDK multipart upload + client-side hashing (`upload_document`, `check_duplicate`, `hash_file`) | Done |
| 6.5 | Bulk upload CLI command (`opencase document bulk-ingest` — walk directory, client-side pre-hash dedup, per-file upload, progress summary) | Done |
| 6.9 | Configuration + env vars (S3Settings: `max_upload_bytes`, `spool_threshold_bytes`) | Done |
| 6.14 | Configuration + env vars (IngestionSettings: `allowed_types_file`, `allowed_content_types`, `allowed_extensions`, ingestion-config API endpoint) | Done |
| 6.1 | DB models + migration (documents table — metadata, SHA-256 hash, matter association, MinIO path, ingestion status; seed global knowledge matter) | Done |
| 6.2 | Global knowledge matter (well-known system matter_id for CPL, case law, court rules — accessible to all users) | Done |
| 6.3 | Manual upload Celery task (SHA-256 dedup, legal hold, store to MinIO, trigger extraction) | Pending |
| 6.6 | Document listing/status API endpoint (read-only — query documents by matter, ingestion status, metadata) | Pending |
| 6.7 | Cloud ingestion Celery task (SharePoint via Graph API) | Pending |
| 6.8 | Cloud ingestion Beat schedule (15-min polling interval) | Pending |
| 6.10 | Observability (ingestion spans/metrics) | Pending |
| **7.0** | **Chatbot / Q&A** | **Pending** |
| 7.1 | DB models + migration (chat_queries, conversation_history, feedback tables) | Pending |
| 7.2 | LLM inference model setup (Ollama model pull — Llama 3 8B / Mistral 7B, health check) | Pending |
| 7.3 | Matter-scoped RAG query API endpoint (LangChain + Qdrant retrieval + Ollama inference, wired up via FastAPI) | Pending |
| 7.4 | Minimal chat interface (CLI command or lightweight web UI for testing/demo) | Pending |
| 7.5 | Citation assembly | Pending |
| 7.6 | AI disclaimer | Pending |
| 7.7 | Conversation history | Pending |
| 7.8 | Audit logging of queries (metadata + reference ID → audit log, full query/response → chat_queries table) | Pending |
| 7.9 | User feedback API endpoints (submit: thumbs up/down, flag bad citations; query: filter by matter/date for analysis) | Pending |
| 7.10 | Configuration + env vars (ChatbotSettings — system prompt, model selection, temperature, max tokens, chunk retrieval count) | Pending |
| 7.11 | Observability (RAG query times, LLM response times, failed queries) | Pending |
| **8.0** | **Audit Logging** | **Pending** |
| 8.1 | DB models + migration (audit_log table — hash-chained entries) | Pending |
| 8.2 | Hash-chained log | Pending |
| 8.3 | Nightly chain validation | Pending |
| 8.4 | Audit log API endpoints (read-only — query, filter by event type/date/user/matter, export as PDF/CSV) | Pending |
| 8.5 | Configuration + env vars (AuditSettings — retention period, chain validation schedule, export formats) | Pending |
| **9.0** | **RBAC & MFA** | **Pending** |
| 9.1 | DB models + migration (roles, user-role mapping, matter-user assignments, permissions) | Pending |
| 9.2 | Auth API endpoints (login, logout, refresh, MFA setup/verify) | Pending |
| 9.3 | JWT authentication | Pending |
| 9.4 | MFA (TOTP) | Pending |
| 9.5 | User management API endpoints (CRUD users, assign roles) | Pending |
| 9.6 | Four roles (Admin, Attorney, Paralegal, Investigator) | Pending |
| 9.7 | Matter assignment API endpoints (assign/revoke user-matter access) | Pending |
| 9.8 | Work product visibility | Pending |
| 9.9 | Session management (httpOnly cookies) | Pending |
| 9.10 | Auth audit trail (role changes, permission grants, matter assignment changes → audit log) | Pending |
| 9.11 | Observability (login/logout, failed attempts, MFA challenges, session metrics) | Pending |
| 9.12 | Configuration + env vars (AuthSettings — token expiry, refresh TTL, MFA window, lockout policy) | Pending |
| **R.0** | **Release Engineering (post-RC)** | **Pending** |
| R.1 | `backend/app/__version__.py` as single source of truth | Pending |
| R.2 | Container image tagged with version (not just git SHA) | Pending |
| R.3 | GitHub release workflow (tag → build → push to GHCR) | Pending |
| R.4 | Operationalized update process (upgrade path for deployed firms) | Pending |
