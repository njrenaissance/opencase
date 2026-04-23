# Gideon Documentation

## Table of Contents

### Architecture

- [Architecture Overview](ARCHITECTURE.md) — Services,
  network topology, module structure, data flows,
  permission model, security invariants

### Data Flows

- [Document Ingestion](flows/ingestion.md) — Upload → parsing → chunking → vectorization → storage
- [RAG Query](flows/rag-query.md) — User question → retrieval → LLM call → citations → audit log
- [Authentication](flows/authentication.md) — Login → JWT → session → MFA verification
- [Permission Filtering](flows/permission-filtering.md) — Query → `build_permission_filter()` → matter-scoped results
- [Background Jobs](flows/background-jobs.md) — Cloud ingestion, deadline monitoring, audit validation, legal hold enforcement

### Planning

- [Feature Roadmap](FEATURES.md) — Prioritized feature
  list with spec and implementation status

### Specifications

*Coming soon — feature specifications and Gherkin
BDD scenarios.*

### Guides

- [Authentication](AUTHENTICATION.md) — JWT login flow,
  TOTP MFA setup, token strategy, account lockout,
  admin bootstrap
- [Observability](OBSERVABILITY.md) — OTel strategy,
  traces/metrics/logs instrumentation, Grafana otel-lgtm
- [Background Tasks](TASKS.md) — Celery architecture, task
  registry, adding new tasks, result backend

### Reference

- [CLI Reference](CLI.md) — Complete CLI command reference,
  all flags, examples, and configuration
- [Settings Reference](SETTINGS.md) — all environment variables,
  defaults, and configuration classes
- [Infrastructure Reference](INFRASTRUCTURE.md) — Docker Compose
  services, ports, volumes, and integration test stack
- [Entity Relationship Diagram](ERD.md) — database schema
  (Feature 1.2 tables; updated each feature)

### History

- [Development Journal](DEVELOPERS_LOG.md) — running log of the development
  process, decisions, and lessons learned

### Legal Framework

- [Third-Party Licenses](../LICENSING.md) — component
  license inventory and compatibility analysis

*Coming soon — jurisdiction-specific discovery rules,
compliance references, and domain glossary.*
