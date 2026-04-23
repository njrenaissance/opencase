# Contributing to Gideon

Thank you for your interest in contributing to Gideon.
This project serves criminal defense attorneys who need
privacy-first discovery tooling, and every contribution
helps level the playing field.

## Who Can Contribute

Gideon welcomes contributors of all kinds:

- **Developers** — Python, TypeScript, DevOps
- **Legal professionals** — domain knowledge, workflow
  expertise, jurisdiction-specific rule sets, test case
  scenarios
- **Security researchers** — review of access controls,
  audit logging, and data isolation
- **Technical writers** — documentation, guides, legal
  framework references

## Getting Started

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Run linting and tests (see below)
5. Submit a pull request

## Development Setup

The repository contains multiple projects: `backend/` (FastAPI), `frontend/`
(Next.js), `shared/` (shared utilities), `sdk/` (Python SDK), and `cli/`
(command-line interface).

### Prerequisites

- **Git**
- **Python 3.12+** with `uv` (for unit tests and linting)
- **Docker** (optional, required only for integration tests)
  - **Windows**: Use [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Quick Start

1. Clone the repository:

   ```bash
   git clone https://github.com/njrenaissance/gideon.git
   cd gideon
   ```

2. Sync Python dependencies (creates `.venv/` with all dependency groups):

   ```bash
   uv sync --all-groups
   ```

3. Run unit tests and linting:

   ```bash
   # Format code with ruff
   uv run ruff format backend/

   # Lint with ruff
   uv run ruff check backend/

   # Run unit tests
   uv run pytest backend/tests/
   ```

### Integration Tests (Optional)

Integration tests require Docker and the backend image to be built locally.

1. Build the backend Docker image:

   ```bash
   docker build -f infrastructure/Dockerfile.backend -t gideon-backend:dev .
   ```

2. Run integration tests:

   ```bash
   uv run pytest backend/tests/ -m integration
   ```

   Or use the integration Compose file to spin up a full stack:

   ```bash
   docker compose -f infrastructure/docker-compose.integration.yml up -d
   uv run pytest backend/tests/
   docker compose -f infrastructure/docker-compose.integration.yml down
   ```

For a persistent local environment (non-development), see
[LOCAL_DEPLOYMENT.md](docs/LOCAL_DEPLOYMENT.md).

## Git Workflow

### Branch Naming

Use short-lived branches named with the pattern:
`<type>/<issue-number>-<description>`

Examples:

- `feature/42-bulk-send-api`
- `fix/118-fix-qdrant-filter-bypass`
- `docs/116-overhaul-quickstart`

Each branch should address a single GitHub issue.

### Commit Size

Keep commits small and focused — one logical change per commit. This makes history easy to review, bisect, and understand.

### Conventional Commits

Follow the [Conventional Commits](https://www.conventionalcommits.org/)
specification:

- **Format:** `<type>[optional scope]: <description>`
- **Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
  `build`, `ci`, `chore`, `revert`
- **Breaking changes:** Append `!` after the type (e.g., `feat!: redesign
  API`) or include `BREAKING CHANGE:` in the footer. This triggers a major
  version bump in automated releases.

**Examples:**

- `feat: add bulk send feature` → minor version bump (0.X.0)
- `fix(auth): resolve login timeout issue` → patch version bump (0.0.X)
- `docs: update API documentation` → patch version bump (0.0.X)
- `feat!: redesign authentication flow` → major version bump (X.0.0)

### Issue Tracking

Track work via GitHub Issues, not TODO comments in code. Use the provided
issue templates when creating new issues:

- [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md)
- [Feature Request](.github/ISSUE_TEMPLATE/feature_request.md)

When referencing an issue in a commit, use `fixes #123` or `relates to #123`
in the commit message footer.

## Security

If you discover a security vulnerability, **do not open
a public issue.** Instead, see [SECURITY.md](SECURITY.md)
for responsible disclosure instructions.

Given the sensitivity of the data Gideon handles
(criminal defense discovery materials), security review
of all contributions is thorough and non-negotiable.

## Non-Negotiable Rules

These cannot be relaxed by any contribution:

1. No third-party LLM API calls
2. No model training on client data
3. No external telemetry — keep all observability
   (traces, metrics, logs) on-premise
4. All vector queries must be limited to matter scope
   (enforced via `build_permissions_filter()`)
5. Legal hold = immutable documents
6. SHA-256 hash on every ingested document
7. Immutable hash-chained audit log

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for the full Code of Conduct.

## License

By contributing, you agree that your contributions will be licensed under the
Apache 2.0 license. See [LICENSING.md](docs/LICENSING.md) for details.
