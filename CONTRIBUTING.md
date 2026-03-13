# Contributing to OpenCase

Thank you for your interest in contributing to OpenCase.
This project serves criminal defense attorneys who need
privacy-first discovery tooling, and every contribution
helps level the playing field.

## Who Can Contribute

OpenCase welcomes contributors of all kinds:

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

*Coming soon — Docker Compose development environment
instructions.*

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
a public issue.** Instead, email the maintainers
directly. Details in SECURITY.md (coming soon).

Given the sensitivity of the data OpenCase handles
(criminal defense discovery materials), security review
of all contributions is thorough and non-negotiable.

## Non-Negotiable Rules

These cannot be relaxed by any contribution:

1. No third-party LLM API calls
2. No model training on client data
3. No telemetry
4. `build_qdrant_filter()` on every vector query
5. Legal hold = immutable documents
6. SHA-256 hash on every ingested document
7. Immutable hash-chained audit log
8. MFA enforced for all users
9. Encryption at rest and in transit

## Code of Conduct

Be respectful, constructive, and professional. This
project serves people whose liberty depends on effective
legal representation. We take that responsibility
seriously.

## License

By contributing, you agree that your contributions will
be licensed under the [Apache 2.0](LICENSE) license.
