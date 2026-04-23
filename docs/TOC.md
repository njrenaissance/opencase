# Gideon Documentation

## Table of Contents

### Architecture

- [Architecture Overview](ARCHITECTURE.md) — Services,
  network topology, module structure, data flows,
  permission model, security invariants

### Data Flows

- [Document Ingestion](flows/ingestion.md) — Upload → parsing → chunking →
  vectorization → storage
- [RAG Query](flows/rag-query.md) — User question → retrieval → LLM call →
  citations → audit log
- [Authentication](flows/authentication.md) — Login → JWT → session → MFA
  verification
- [Permission Filtering](flows/permission-filtering.md) — Query →
  `build_permission_filter()` → matter-scoped results
- [Background Jobs](flows/background-jobs.md) — Cloud ingestion, deadline
  monitoring, audit validation, legal hold enforcement

### Planning

- [Feature Roadmap](ROADMAP.md) — Prioritized feature
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
- [Deployment](DEPLOYMENT.md) — Production deployment strategies
  and infrastructure considerations
- [Local Deployment](LOCAL_DEPLOYMENT.md) — Running Gideon locally
  with Docker Compose for development and testing

### Reference

- [Settings Reference](SETTINGS.md) — all environment variables,
  defaults, and configuration classes
- [Infrastructure Reference](INFRASTRUCTURE.md) — Docker Compose
  services, ports, volumes, and integration test stack
- [Entity Relationship Diagram](ERD.md) — database schema
  (Feature 1.2 tables; updated each feature)
- [CLI Reference](../cli/README.md) — command-line tool reference
- [SDK Reference](../sdk/README.md) — Python SDK documentation

### Legal Framework

- [Compliance & Legal](LEGAL_COMPLIANCE.md) — ABA rules,
  jurisdiction-specific requirements (NY CPL, FRCP), Brady/Giglio,
  Jencks material gating
- [Third-Party Licenses](LICENSING.md) — component
  license inventory and compatibility analysis

*Coming soon — jurisdiction-specific discovery rules,
domain glossary.*
