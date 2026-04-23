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

Major releases are named after famous jurists. For details on versioning and
release management, see [VERSIONING.md](VERSIONING.md).

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

## Project Structure

```text
gideon/
├── backend/              # FastAPI application (REST API, auth, RAG, celery integration)
├── cli/                  # Command-line interface (built on SDK)
├── docs/                 # User-facing documentation (architecture, guides, references)
├── frontend/             # Next.js application (UI, session management) — in development
├── infrastructure/       # Docker Compose configuration and init scripts
├── scripts/              # Operational and testing scripts (data management, RAG testing)
├── sdk/                  # Python SDK for programmatic access to Gideon API
├── shared/               # Shared Python utilities (models, exceptions, helpers)
├── .github/workflows/    # CI/CD pipelines (linting, tests, container builds)
└── pyproject.toml        # Root versioning (single source of truth for all projects)
```

| Directory | Purpose |
| --- | --- |
| `/backend` | **Python project.** FastAPI REST API, JWT authentication, RBAC, audit logging, LangChain RAG pipeline, Celery task submission |
| `/cli` | **Python project.** Command-line tool built on the Python SDK; enables programmatic document ingestion and queries |
| `/docs` | User documentation: architecture diagrams, data flow guides, deployment instructions, legal compliance, settings reference |
| `/frontend` | Next.js React app (UI in development); will proxy to FastAPI and manage httpOnly session cookies |
| `/infrastructure` | Docker Compose services, init scripts, volume/network setup, CI/CD workflows |
| `/scripts` | Utility scripts for document upload, bulk ingestion, RAG testing, database queries, and local deployment |
| `/sdk` | **Python project.** SDK providing `Client` and `Session` for API access; used by CLI and external tools |
| `/shared` | **Python project.** Reusable Python models, exceptions, validators, and helpers shared across backend, SDK, CLI |

## Hardware Requirements

| Tier | RAM | CPU | Storage | GPU |
| --- | --- | --- | --- | --- |
| Minimum | 16 GB | 8 cores | 500 GB | None (CPU-only) |
| Recommended | 32 GB | 8 cores | 500 GB | NVIDIA 16+ GB VRAM |

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

Workflows live in `.github/workflows/` at the repo root (GitHub Actions only
reads from this path). CI currently covers only the `backend/` service — all
jobs are scoped via `working-directory` and path filters.

### Workflows and Jobs

| Workflow | Trigger | Jobs | Purpose |
| --- | --- | --- | --- |
| `ci.yml` | PR to main; manual dispatch | **Setup Docker Volumes** → **Lint & Format** → **Unit Tests** | Core pipeline: prepares test environment, checks code quality, runs unit tests with coverage |
| `format-lint.yml` | Called by ci.yml; manual dispatch | Ruff format check, ruff lint, mypy (backend, shared, sdk, cli) | Validates code formatting and type safety across all Python projects |
| `unit-tests.yml` | Called by ci.yml; manual dispatch | pytest (backend, shared, sdk, cli) with coverage | Runs unit tests (excludes integration tests) and enforces 70% minimum coverage |
| `build-container.yml` | Manual dispatch only | Build & Push Container | Builds backend Docker image and pushes to GHCR with tags (latest, commit SHA, branch/PR refs). Requires manual trigger via **Actions > Build Container > Run workflow** |
| `ai-code-review.yml` | PR open (non-draft) | AI Code Review | Delegates to public `njrenaissance/pr-review-agent` for automated code review |

### Required GitHub Secrets

| Secret | Workflow | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | `ai-code-review.yml` | Anthropic API for code review |

`GITHUB_TOKEN` is provided automatically by GitHub Actions and requires no
configuration.

## Status

Early development. Not yet suitable for production use.

## License

[Apache 2.0](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Documentation

See [docs/TOC.md](docs/TOC.md) for full documentation
index.

## Getting Started

**For development:** See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and
test instructions.

**For local deployment:** See [docs/LOCAL_DEPLOYMENT.md](docs/LOCAL_DEPLOYMENT.md)
for instructions on running a persistent Gideon instance.

**For operational and testing scripts:** See [scripts/README.md](scripts/README.md)
for a complete reference of available scripts.
