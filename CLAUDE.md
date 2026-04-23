# Gideon — Claude Code Context

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

## Architecture Overview

### Deployment Model

- **Single-tenant**: one Gideon instance per firm
- **Two modes**:
  - *Air-gapped*: manual upload only, no external
    network calls
  - *Internet-accessible*: firm-controlled server or
    private cloud VPC; enables optional scheduled cloud
    storage ingestion
- **Eleven Docker Compose services** (see below)

### Service Topology

```text
Browser → Next.js → FastAPI → PostgreSQL
                             → Qdrant
                             → MinIO (S3)
                             → Ollama
                             → Worker Queue ┐
                               ├ Redis      │
                               ├ Celery Worker
                               ├ Celery Beat│
                               ├ Flower     │
                               └ PostgreSQL (tasks)
                                            ┘
```

| Service | Role |
| --- | --- |
| Next.js | UI, session management, httpOnly cookie, proxies to FastAPI |
| FastAPI | API, JWT auth, RBAC, audit logging, LangChain RAG (in-process) |
| MinIO | S3-compatible object store for original documents |
| Ollama | Local LLM + embeddings (Llama 3 8B / Mistral 7B; nomic-embed-text) |
| PostgreSQL (API) | Relational store — matters, documents, users, audit log, metadata |
| PostgreSQL (tasks) | Worker Queue task lifecycle records — separate instance for fault isolation |
| Qdrant | Vector store — single collection, permission-filtered on every query |
| Redis | Task queue (Celery broker) + cache |
| Celery Worker | Background task execution — ingestion, deadlines, audit, legal hold |
| Celery Beat | Scheduled task submission (cron-based) |
| Flower | Celery monitoring UI (queue depth, worker status, task management) |

**FastAPI is never exposed on a public port.**
Only Next.js can reach it from outside the Docker
network.

**LangChain runs inside FastAPI as a library** — it is
not a separate service.

---

## Tech Stack

| Component | Decision |
| --- | --- |
| Frontend | Next.js (React), TypeScript |
| API | FastAPI (Python) |
| RAG | LangChain (in-process within FastAPI) |
| Vector DB | Qdrant |
| LLM runtime | Ollama |
| Default LLM | Llama 3 8B or Mistral 7B |
| Embedding model | nomic-embed-text via Ollama |
| Document storage | MinIO (S3-compatible object store) |
| Relational DB | PostgreSQL |
| Background jobs | Celery + Redis (Celery Beat for scheduling) |
| Document parsing | Apache Tika + Tesseract OCR |
| Cloud ingestion | Microsoft Graph API (SharePoint) |
| Deployment | Docker Compose |
| Container base | Debian slim (`python:3.12-slim`, `node:22-slim`) |
| Container pattern | Two-stage builds (builder + runtime), non-root user |
| Testing (BDD) | pytest-bdd, Gherkin `.feature` files |

---

## Security & Privacy Rules — Non-Negotiable

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

## Permission Model

### Roles

| Role | Work product | Jencks material | Matter access |
| --- | --- | --- | --- |
| Admin | Yes | Yes | All matters |
| Attorney | Yes | Yes | Assigned matters |
| Paralegal | If `view_work_product` granted | Yes | Assigned matters |
| Investigator | No | No | Assigned matters |

### Vector Payload (every chunk in Qdrant carries these fields)

```json
{
  "firm_id": "uuid",
  "matter_id": "uuid",
  "client_id": "uuid",
  "document_id": "uuid",
  "chunk_index": 0,
  "classification": "brady|giglio|jencks|rule16|work_product|inculpatory|unclassified",
  "source": "government_production|defense|court|work_product",
  "bates_number": "string|null",
  "page_number": 4
}
```

### Jencks Rule

Jencks material is filtered from all queries until
`has_testified = true` is set on the witness record for
that matter. This flag lives in PostgreSQL and is checked
inside `build_permissions_filter()`.

---

## FastAPI Module Structure

```text
backend/
└── app/
    ├── api/          # routers
    ├── core/         # auth, permissions, audit
    ├── storage/      # MinIO S3 client
    ├── rag/          # pipeline, embedder, citations
    ├── ingestion/    # parser, chunker, deduplicator
    ├── workers/      # celery tasks
    └── db/           # models, session
```

---

## Background Jobs (Celery Beat Schedule)

| Job | Schedule | Purpose |
| --- | --- | --- |
| Cloud ingestion worker | Every 15 min | Poll Graph API, ingest, delete temp files |
| Deadline monitor | Every 1 hour | CPL 245 and CPL 30.30 clock alerts |
| Audit chain validator | Nightly | Verify hash chain integrity |
| Legal hold enforcer | Continuous | Block deletion on held documents |

**Temp file handling:** Celery worker uses an ephemeral
named volume (`celery-tmp`). Each file is deleted
immediately after ingestion completes or fails. A startup
cleanup job wipes orphaned files from any previous
crashed run.

---

## MVP Features (V1) — Priority Order

1. **Document ingestion** — manual upload + scheduled
   cloud sync
2. **Chatbot / Q&A** — matter-scoped RAG, citations,
   fully audit logged
3. **Brady/Giglio tracker** — CPL 245 clocks,
   demand/response log, dashboard
4. **Document viewer & review** — hit highlighting,
   batch tagging, notes
5. **Witness index** — entity extraction, Giglio flagging
6. **RBAC & MFA** — four roles: Admin, Attorney,
   Paralegal, Investigator
7. **Audit logging** — hash chain, PDF/CSV export

## V2 Features (out of scope for now)

Bulk ingestion, email threading, case timeline,
redaction, work product notes, matter templates, export
package, body cam metadata, protective order tracker,
temporary elevated access.

## V3 Features (out of scope for now)

Multi-jurisdiction, predictive coding, Kubernetes/Helm,
client portal, Clio integration, Spanish language, HIPAA
module, lab report analysis, grand jury materials.

---

## Scope Constraints

- English only
- US criminal defense
- NY State + Federal courts (NY CPL Article 245,
  CPL 30.30, Brady, Giglio, Jencks Act, FRCP 16)
- Not a billing system, client portal, or general case
  management platform

---

## BDD Test Structure

Tests are written in Gherkin and executed with
`pytest-bdd`.

```text
backend/
└── tests/
    ├── features/
    │   ├── ingestion/
    │   ├── chatbot/
    │   ├── brady_tracker/
    │   ├── document_review/
    │   ├── witness_index/
    │   ├── rbac/
    │   └── audit/
    └── step_defs/
        ├── ingestion/
        ├── chatbot/
        └── ...
```

Each `.feature` file maps to one MVP feature area. Step
definitions live in matching subdirectories under
`step_defs/`.

---

## Code Style

- **DRY principle**: If extracting shared code reduces
  administrative overhead (fewer places to update when
  something changes), do it. Prefer shared helpers,
  context managers, and base utilities over copy-paste.

## Test Style

- Use parametrized tests when testing the same outcome
  across different fields or inputs. Do not write
  separate test functions that only differ by which
  field has a bad value. In Python use
  `@pytest.mark.parametrize`; in TypeScript use
  `it.each` (vitest).
- Use fixtures and shared helpers (in `conftest.py`) to
  reduce boilerplate. Repeated setup/teardown logic
  should be extracted into context managers or fixtures
  rather than duplicated in every test function.
- **Pre-commit dedup check**: Before committing, review
  all files in the changeset for functions that share
  the same name, signature, and purpose. If duplicates
  exist across files, collapse them into a single shared
  function in the appropriate shared module (e.g.
  `tests/factories.py` for test helpers). Do not commit
  files containing duplicate function definitions.

---

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

Keep commits small and focused — one logical change per commit. This makes
history easy to review, bisect, and understand.

### Conventional Commits

Follow the [Conventional Commits](https://www.conventionalcommits.org/)
specification:

- **Format:** `<type>[optional scope]: <description>`
- **Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
  `build`, `ci`, `chore`, `revert`
- **Breaking changes:** Append `!` after the type (e.g., `feat!: redesign
  API`) or include `BREAKING CHANGE:` in the footer. **IMPORTANT:** When
  the user indicates a change is breaking (API changes, removed features,
  incompatible updates), always include `!` after the type or
  `BREAKING CHANGE:` in the footer. This triggers a major version bump in
  automated releases.

**Examples:**

- `feat: add bulk send feature` → minor version bump (0.X.0)
- `fix(auth): resolve login timeout issue` → patch version bump (0.0.X)
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
