# Gideon

[![CI Pipeline](https://github.com/njrenaissance/gideon/actions/workflows/ci.yml/badge.svg)](https://github.com/njrenaissance/gideon/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Open source criminal defense discovery platform.**

A free, fully self-hostable, AI-powered discovery platform for
solo and small criminal defense practitioners. Runs entirely
on-premise with no third-party LLM API calls, protecting client
confidentiality under ABA Rules 1.6 and 1.1.

> **Legal Disclaimer:** Gideon is a software tool, not legal advice. See [DISCLAIMER.md](DISCLAIMER.md).

## Mission

Named after *Gideon v. Wainwright* (1963) — the Supreme Court
decision establishing the constitutional right to effective
counsel for criminal defendants who cannot afford an attorney.

The principle is simple: **a defendant's right to counsel is
meaningless without the tools to mount an effective defense.**

Large law firms have access to enterprise eDiscovery platforms
(Relativity, Concordance, etc.). Solo practitioners and small
criminal defense firms do not. This creates a two-tier system
where a defendant's access to quality discovery analysis depends
on their attorney's budget — not the strength of their case.

Gideon exists to level that playing field. It's built on two
commitments:

1. **Data stays on-premise** — Client confidentiality is
   non-negotiable. No third-party APIs, no cloud ingestion,
   no telemetry. Your discovery materials never leave your
   infrastructure.

2. **Free and open source** — No licensing fees, no vendor
   lock-in, no proprietary black boxes. You own your data and
   your tools.

## Release Naming Convention

Major releases are named after famous jurists:

| Version | Codename | Jurist |
| --- | --- | --- |
| v1.0 | Ginsburg | Ruth Bader Ginsburg |

## Key Features (MVP)

1. **Document ingestion** — PDF, Word, email, images
   with OCR; manual upload or scheduled cloud sync
2. **Chatbot / Q&A** — matter-scoped RAG with citations
   and audit logging
3. **Brady/Giglio tracker** — demand/response log,
   CPL 245 and CPL 30.30 clocks
4. **Document viewer** — hit highlighting, batch
   tagging, classification
5. **Witness index** — entity extraction, Giglio flagging
6. **RBAC & MFA** — Admin, Attorney, Paralegal,
   Investigator roles
7. **Audit logging** — immutable hash-chained log,
   PDF/CSV export

## Technology Stack

Eleven Docker Compose services running on commodity
hardware:

- **Next.js** — UI and session management
- **FastAPI** — API, auth, RAG pipeline (LangChain)
- **MinIO** — S3-compatible document object storage
- **Ollama** — local LLM inference and embeddings
- **PostgreSQL** — relational data store
- **Qdrant** — permission-filtered vector search
- **Redis** — task queue broker
- **Celery + Beat + Flower** — background workers and monitoring
- **Grafana LGTM** — local observability (traces, metrics, logs)

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for
full details.

## Hardware Requirements

| Tier | RAM | CPU | Storage | GPU |
| --- | --- | --- | --- | --- |
| Minimum | 16 GB | 8 cores | 500 GB | None (CPU-only) |
| Recommended | 32 GB | 8 cores | 500 GB | NVIDIA 16+ GB VRAM |

## Quick Start

**For development:** See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and
test instructions.

**For local deployment:** See [LOCAL_DEPLOYMENT.md](LOCAL_DEPLOYMENT.md) for instructions
on running a persistent Gideon instance.

## Scripts

Operational and testing scripts live in `scripts/` and are run from the repo
root. All Python scripts read credentials and configuration from `.env` via
`dotenv`.

### Task & Document Testing

| Script | Purpose |
| --- | --- |
| `submit_task.py` | Submit a ping task and a 30-second sleep task via the API; poll until completion. Useful for testing Celery worker connectivity. |
| `upload_file.py` | Upload a file (or auto-generated test file) to the first matter, then verify the DB record, S3 object, and download round-trip. |

### Data Management

| Script | Purpose |
| --- | --- |
| `chunk_documents.py` | Submit chunking tasks for existing documents. Reads extracted text from S3 and submits tasks via the API. Supports `--limit` flag. |
| `reset_data.py` | Reset all application data (PostgreSQL, MinIO, Qdrant). Truncates user-data tables, empties MinIO bucket, deletes Qdrant collection. Use `--skip-db`, `--skip-s3` to reset selectively. |

### RAG & Search Testing

| Script | Purpose |
| --- | --- |
| `rag_query.py` | End-to-end RAG query against Gideon stack (runs inside FastAPI container). Embeds query, searches Qdrant, retrieves context, calls Ollama for inference. Requires `--matter-id` and `--firm-id`. |
| `search_qdrant.py` | Semantic search against Qdrant vector store (runs inside FastAPI container). Embeds query, searches, retrieves chunk text from MinIO. |
| `query_model.py` | Query an Ollama model directly (no RAG, no Qdrant). Baseline comparison for `rag_query.py` results. Use `--model`, `--system-prompt`, `--max-tokens` flags. |
| `eval_models.py` | Evaluate exported RAG prompts against multiple Ollama models. Takes JSON from `rag_query.py --export-prompt`. Use `--baseline` flag to compare RAG vs bare-question results. |

## Privacy & Security

All data stays on your infrastructure — no third-party LLM APIs,
no telemetry, no model training on client data. Full details in
[SECURITY.md](SECURITY.md) and [CONTRIBUTING.md](CONTRIBUTING.md)
(Non-Negotiable Rules section).

## Target Users

- Solo criminal defense attorneys
- Small criminal defense firms (2-10 attorneys)
- Article 18B assigned counsel
- Public defender offices without enterprise tooling
- Law clinics and legal aid organizations

## Jurisdictions

- New York State (CPL Article 245, CPL 30.30)
- Federal (FRCP Rule 16, Brady, Giglio, Jencks Act)

## CI

Workflows live in `.github/workflows/` at the repo root
(GitHub Actions only reads from this path). CI currently
covers only the `backend/` service — all jobs are scoped
via `working-directory` and path filters.

Pull requests run the full pipeline via GitHub Actions:
lint → unit tests → container build.

AI code review runs separately on PR open.

### Required GitHub Secrets

| Secret | Workflow | Purpose |
| --- | --- | --- |
| `GH_PAT` | `ai-code-review.yml` | Clone `SignaTrustDev/pr-review-agent` |
| `ANTHROPIC_API_KEY` | `ai-code-review.yml` | Anthropic API for review |

`GITHUB_TOKEN` is provided automatically by GitHub
Actions and requires no configuration.

## Status

Early development. Not yet suitable for production use.

## License

[Apache 2.0](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Documentation

See [docs/TOC.md](docs/TOC.md) for full documentation
index.
