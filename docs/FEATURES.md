# OpenCase Feature Roadmap

## Priority 0 — Project Scaffolding

| ID | Feature | Status |
| --- | --- | --- |
| 0.1 | FastAPI skeleton (health endpoint, package structure) | Done |
| 0.2 | AppConfiguration (JSON + env via pydantic-settings) | Done |
| 0.3 | Logging (Python logging, level from AppConfiguration) | Pending |
| 0.4 | Observability (OpenTelemetry traces/spans, metrics) | Pending |
| 0.5 | Backend Dockerfile (run app for integration testing) | Pending |
| 0.6 | `.env.example` | Pending |
| 0.7a | CI: `format-lint.yml` (ruff) | Pending |
| 0.7b | CI: `unit-tests.yml` (pytest @unit) | Pending |
| 0.7c | CI: `integration-tests.yml` (pytest @integration) | Pending |
| 0.7d | CI: `ai-code-review.yml` (same as Signatrust_v4) | Pending |
| 0.7e | CI: `build-container.yml` (on spec/code change) | Pending |

## Priority 1 — API

| ID | Feature | Specs | Code |
| --- | --- | --- | --- |
| 1.0 | OpenAPI specification (openapi.yml) | Pending | Pending |
| 1.1 | Authentication (JWT, sessions, login/logout) | Pending | Pending |

## Priority 2 — Document Ingestion

| ID | Feature | Specs | Code |
| --- | --- | --- | --- |
| 2.1 | Manual upload (PDF, Word, email, images) | Done | Pending |
| 2.2 | Text extraction + OCR (Tika/Tesseract) | Done | Pending |
| 2.3 | Chunking + embedding (Qdrant) | Done | Pending |
| 2.4 | SHA-256 deduplication | Done | Pending |
| 2.5 | S3 document storage (MinIO) | Done | Pending |
| 2.6 | Cloud ingestion (OneDrive/SharePoint) | Done | Pending |
| 2.7 | Legal hold enforcement | Done | Pending |

## Priority 3 — Chatbot / Q&A

| ID | Feature | Specs | Code |
| --- | --- | --- | --- |
| 3.1 | Matter-scoped RAG query | Pending | Pending |
| 3.2 | Citation assembly | Pending | Pending |
| 3.3 | AI disclaimer | Pending | Pending |
| 3.4 | Conversation history | Pending | Pending |
| 3.5 | Audit logging of queries | Pending | Pending |

## Priority 4 — Brady/Giglio Tracker

| ID | Feature | Specs | Code |
| --- | --- | --- | --- |
| 4.1 | CPL 245 disclosure clocks | Pending | Pending |
| 4.2 | CPL 30.30 speedy trial clock | Pending | Pending |
| 4.3 | Demand/response log | Pending | Pending |
| 4.4 | Brady/Giglio classification | Pending | Pending |
| 4.5 | Deadline alerts | Pending | Pending |

## Priority 5 — Document Viewer & Review

| ID | Feature | Specs | Code |
| --- | --- | --- | --- |
| 5.1 | Document retrieval from S3 | Pending | Pending |
| 5.2 | Hit highlighting | Pending | Pending |
| 5.3 | Batch tagging | Pending | Pending |
| 5.4 | Notes/annotations | Pending | Pending |
| 5.5 | Bates number display | Pending | Pending |

## Priority 6 — Witness Index

| ID | Feature | Specs | Code |
| --- | --- | --- | --- |
| 6.1 | Entity extraction | Pending | Pending |
| 6.2 | Giglio flagging | Pending | Pending |
| 6.3 | Jencks material gating | Pending | Pending |
| 6.4 | Witness-document linking | Pending | Pending |

## Priority 7 — RBAC & MFA

| ID | Feature | Specs | Code |
| --- | --- | --- | --- |
| 7.1 | JWT authentication | Pending | Pending |
| 7.2 | MFA (TOTP) | Pending | Pending |
| 7.3 | Four roles (Admin, Attorney, Paralegal, Investigator) | Pending | Pending |
| 7.4 | Matter assignment | Pending | Pending |
| 7.5 | Work product visibility | Pending | Pending |
| 7.6 | Session management (httpOnly cookies) | Pending | Pending |

## Priority 8 — Audit Logging

| ID | Feature | Specs | Code |
| --- | --- | --- | --- |
| 8.1 | Hash-chained log | Pending | Pending |
| 8.2 | Nightly chain validation | Pending | Pending |
| 8.3 | PDF/CSV export | Pending | Pending |
| 8.4 | Event type filtering | Pending | Pending |
