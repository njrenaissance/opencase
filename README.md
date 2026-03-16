# OpenCase

**Open source criminal defense discovery platform.**

A free, fully self-hostable, AI-powered discovery
platform for solo and small criminal defense
practitioners. Runs entirely on-premise with no
third-party LLM API calls, protecting client
confidentiality under ABA Rules 1.6 and 1.1.

## Why OpenCase?

Solo and small-firm criminal defense attorneys face
massive government discovery productions without access
to the enterprise eDiscovery tooling available to large
firms. OpenCase levels the playing field with:

- **Semantic search** across entire discovery productions
- **AI-powered Q&A** with citations to source documents
- **Brady/Giglio tracking** with CPL 245 deadline clocks
- **Complete privacy** — no data ever leaves your
  infrastructure

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

Eight Docker Compose services running on commodity
hardware:

- **Next.js** — UI and session management
- **FastAPI** — API, auth, RAG pipeline (LangChain)
- **MinIO** — S3-compatible document object storage
- **Ollama** — local LLM inference and embeddings
- **PostgreSQL** — relational data store
- **Qdrant** — permission-filtered vector search
- **Redis** — task queue broker
- **Celery + Beat** — background workers

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for
full details.

## Hardware Requirements

| Tier | RAM | CPU | Storage | GPU |
| --- | --- | --- | --- | --- |
| Minimum | 32 GB | 8 cores | 500 GB | None (CPU-only) |
| Recommended | 32 GB | 8 cores | 500 GB | NVIDIA 16+ GB VRAM |

## Quick Start

1. Copy the example environment file and edit secrets:

   ```bash
   cp .env.example .env
   # Edit .env — replace every CHANGE_ME value
   ```

2. Start all services:

   ```bash
   docker compose -f infrastructure/docker-compose.yml --env-file .env up -d
   ```

## Privacy & Security

- All data stays on your infrastructure — no exceptions
- No third-party LLM API calls — enforced at
  configuration level
- No model training on client data
- No telemetry
- MFA enforced for all users
- Encryption at rest and in transit
- Immutable hash-chained audit log

## Target Users

- Solo criminal defense attorneys
- Small criminal defense firms (2-10 attorneys)
- Article 18B assigned counsel
- Public defender offices without enterprise tooling
- Law clinics and legal aid organizations

## Jurisdictions

- New York State (CPL Article 245, CPL 30.30)
- Federal (FRCP Rule 16, Brady, Giglio, Jencks Act)

## Status

Early development. Not yet suitable for production use.

## License

[Apache 2.0](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Documentation

See [docs/TOC.md](docs/TOC.md) for full documentation
index.
