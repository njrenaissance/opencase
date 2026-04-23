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

### Prerequisites

- **Docker** + Docker Compose (v2+)
  - **Windows**: Use [Docker Desktop](https://www.docker.com/products/docker-desktop/)
    (includes Docker and Docker Compose)
- **Git**
- **Python 3.12+** with `uv` (for running tests/scripts outside Docker)

### Setup Steps

1. Clone the repository and navigate to the root:

   ```bash
   git clone https://github.com/njrenaissance/gideon.git
   cd gideon
   ```

2. Copy the example environment file and edit secrets:

   ```bash
   cp .env.example .env
   # Edit .env — replace every CHANGE_ME value with your own
   ```

3. Create persistent external Docker volumes (one-time setup):

   ```bash
   docker volume create gideon-postgres-data
   docker volume create gideon-qdrant-data
   docker volume create gideon-ollama-models
   ```

4. Start all services:

   ```bash
   docker compose -f infrastructure/docker-compose.yml --env-file .env up -d
   ```

   ⚠️ **First run** — Ollama downloads and caches LLM models (~5–10 GB).
   This takes 5–10 minutes depending on your internet connection.
   Check progress with `docker compose logs ollama` or wait for the
   `gideon-ollama-1` container to report `Listening on 127.0.0.1:11434`.

### Running Tests (Backend)

From the repo root:

```bash
# Format code with ruff
uv run ruff format backend/

# Lint with ruff
uv run ruff check backend/

# Run BDD tests with pytest-bdd
# (requires dev stack to be running)
uv run pytest backend/tests/
```

For faster iteration, you can run a single test:

```bash
uv run pytest backend/tests/features/ingestion/
```

### Stopping the Dev Stack

```bash
docker compose -f infrastructure/docker-compose.yml down
```

To also remove volumes (careful — deletes data):

```bash
docker compose -f infrastructure/docker-compose.yml down -v
```

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

Track work via GitHub Issues, not TODO comments in code. When referencing
an issue in a commit, use `fixes #123` or `relates to #123` in the commit
message footer.

### Git Worktrees

[Git worktrees](https://git-scm.com/docs/git-worktree) are allowed for
parallel work on multiple issues. Each worktree opens as a separate VS Code
window. Use [Peacock](https://marketplace.visualstudio.com/items?itemName=johnpapa.vscode-peacock)
to color-code windows so you can distinguish them at a glance.

## Code Standards

### Python (Backend)

- Python 3.12+
- Format with `ruff format`
- Lint with `ruff check`
- Type hints required on all public functions
- Tests written as BDD with `pytest-bdd` and Gherkin
  `.feature` files

### TypeScript (Frontend)

- Node.js 20+
- Format with Prettier
- Lint with ESLint
- Strict TypeScript (`strict: true`)

### Markdown

- All `.md` files must pass `markdownlint`
- Line length limit: 80 characters (tables and code
  blocks excluded)
- Fenced code blocks must specify a language

### Git

- Conventional commits: `feat:`, `fix:`, `docs:`,
  `test:`, `chore:`, `refactor:`
- One logical change per commit
- PRs target `main`

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
   (enforced via `build_qdrant_filter()`)
5. Legal hold = immutable documents
6. SHA-256 hash on every ingested document
7. Immutable hash-chained audit log

## Code of Conduct

Be respectful, constructive, and professional. This
project serves people whose liberty depends on effective
legal representation. We take that responsibility
seriously.

## License

By contributing, you agree that your contributions will
be licensed under the [Apache 2.0](LICENSE) license.
