# Gideon

[![CI Pipeline](https://github.com/njrenaissance/gideon/actions/workflows/ci.yml/badge.svg)](https://github.com/njrenaissance/gideon/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Open source criminal defense discovery platform.**

A free, fully self-hostable, AI-powered discovery platform for criminal
defense practitioners. Runs entirely on-premise with no third-party LLM API
calls, protecting client confidentiality under ABA Rules 1.6 and 1.1.

> **Legal Disclaimer:** Gideon is a software tool, not legal advice. See
> [DISCLAIMER.md](DISCLAIMER.md).

## Getting Started

### For Development

Clone the repository and set up your Python environment:

```bash
git clone https://github.com/njrenaissance/gideon.git
cd gideon
uv sync --all-groups
```

Run linting and unit tests:

```bash
uv run ruff format backend/
uv run ruff check backend/
cd backend
uv run pytest tests -m "not integration"
```

There are three other projects that should also be tested: cli, shared, and sdk.

For integration tests, see [CONTRIBUTING.md](CONTRIBUTING.md).

### For Local Deployment

Deploy a persistent Gideon instance with Docker Compose:

See [docs/LOCAL_DEPLOYMENT.md](docs/LOCAL_DEPLOYMENT.md) for full
instructions on running the complete stack.

### For Testing & Operations

See [scripts/README.md](scripts/README.md) for documentation on operational
and testing scripts (document upload, bulk ingestion, RAG testing, etc.).

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

## Technology Stack

Eleven Docker Compose services running on commodity hardware:

- **Next.js** — UI and session management
- **FastAPI** — API, auth, RAG pipeline (LangChain)
- **MinIO** — S3-compatible document object storage
- **Ollama** — local LLM inference and embeddings
- **PostgreSQL** — relational data store
- **Qdrant** — permission-filtered vector search
- **Redis** — task queue broker
- **Celery + Beat + Flower** — background workers and monitoring
- **Grafana LGTM** — local observability (traces, metrics, logs)

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines, including:

- Git workflow (branch naming, conventional commits, issue tracking)
- Code style and testing practices
- Security considerations and non-negotiable rules

## Documentation

- **[docs/TOC.md](docs/TOC.md)** — Full documentation index
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Service topology and
  module structure
- **[docs/LOCAL_DEPLOYMENT.md](docs/LOCAL_DEPLOYMENT.md)** — Running Gideon
  locally with Docker Compose
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — Contribution guidelines and
  developer setup
- **[GOVERNANCE.md](GOVERNANCE.md)** — Project governance, versioning, and
  release process
- **[SECURITY.md](SECURITY.md)** — Security model and privacy guarantees

## CI / Testing

Workflows live in `.github/workflows/` and run automatically on pull requests.

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| `ci.yml` | PR to main | Linting, type checking, unit tests (70% coverage minimum) |
| `format-lint.yml` | Called by ci.yml | Ruff format/lint, mypy across all Python projects |
| `unit-tests.yml` | Called by ci.yml | pytest with coverage reporting |
| `build-container.yml` | Manual dispatch | Build and push backend image to GHCR |
| `ai-code-review.yml` | PR open | Automated code review via external agent |

**Required secret:** `ANTHROPIC_API_KEY` for code review workflow.

## Status

Early development. Not yet suitable for production use. See
[docs/ROADMAP.md](docs/ROADMAP.md) for planned features.

## License

[Apache 2.0](LICENSE)
