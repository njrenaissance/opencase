# Gideon — Claude Code Context

This document provides the context needed to work on Gideon. Read the sections below in order: mission, then security rules (critical), then architecture and technical structure.

---

## Project Mission

Gideon is a free, fully self-hostable, AI-powered
discovery platform for solo and small criminal defense
practitioners. It runs entirely on-premise with no
third-party LLM API calls, protecting client
confidentiality under ABA Rules 1.6 and 1.1.

The project is named after *Gideon v. Wainwright* (1963),
the Supreme Court decision establishing the right to
counsel for criminal defendants who cannot afford an
attorney.

Designed in collaboration with solo criminal defense
practitioners from New York.

License: **Apache 2.0**

---

## Security & Privacy Rules — Non-Negotiable

These rules cannot be relaxed and apply to every code change. Claude must enforce them:

1. **No third-party LLM API calls ever.** Enforced at
   configuration level. Ollama only.
2. **No model training on client data.** Zero retention
   for LLM inference.
3. **No external telemetry.** All observability (traces,
   metrics, logs) stays on-premise; no data sent to
   third-party services.
4. **All vector queries must be limited to matter scope,
   enforced via `build_permissions_filter()`.** This function
   is called on every query without exception. It is never
   bypassed and never accepts client-supplied filter
   parameters. This is the most security-critical function
   in the codebase.
5. **Legal hold = immutable.** Documents under legal hold
   cannot be deleted or modified.
6. **SHA-256 hash on every ingested document** for
   deduplication and integrity.
7. **Immutable hash-chained audit log** for all LLM
   queries, document access, and permission changes.
8. **MFA enforced** for all users from day one.
9. **Encryption at rest and in transit.**

---

## Architecture & Design

For detailed information, see:

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Service topology, deployment model, tech stack, module structure, data flows
- **[docs/AUTHENTICATION.md](docs/AUTHENTICATION.md)** — JWT, MFA, token strategy
- **[docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md)** — Docker Compose services, ports, volumes

---

## Background Jobs

Gideon uses Celery for background task processing (document ingestion, deadline
monitoring, audit validation, legal hold enforcement).

See [docs/TASKS.md](docs/TASKS.md) for Celery architecture, task definitions,
API endpoints, and the scheduled job registry.

---

## MVP Features

See [docs/ROADMAP.md](docs/ROADMAP.md) for the complete feature roadmap including V1, V2, and V3 priorities, status, and implementation details.

---

## Scope Constraints

- English only
- US criminal defense
- NY State + Federal courts (NY CPL Article 245,
  CPL 30.30, Brady, Giglio, Jencks Act, FRCP 16)
- Not a billing system, client portal, or general case
  management platform

---

## BDD Testing

Tests are written in Gherkin (BDD style) and executed with `pytest-bdd`.

See [docs/BDD_TESTS.md](docs/BDD_TESTS.md) for test structure, how to write new
tests, and best practices.

---

## Coding Standards

For code style, testing practices, git workflow, and development standards,
see [docs/coding_standards/](docs/coding_standards/).

---

## Key Legal Compliance References

| Rule | Relevance |
| --- | --- |
| ABA Rule 1.6 | Client confidentiality — drives self-hosting |
| ABA Rule 1.1 | Competence — drives AI accuracy and citations |
| ABA Opinion 512 (2024) | Generative AI use by attorneys |
| NY CPL Article 245 | NY discovery obligations and disclosure clocks |
| CPL 30.30 | Speedy trial clocks |
| Brady v. Maryland | Exculpatory evidence disclosure |
| Giglio v. United States | Witness impeachment material disclosure |
| Jencks Act | Prior statements of government witnesses |
| FRCP Rule 16 | Federal criminal discovery |
| Lorraine v. Markel | Document authentication for digital evidence |
