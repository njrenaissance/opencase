# Gideon Documentation

## Table of Contents

### Architecture

- [Architecture Overview](ARCHITECTURE.md) — Services,
  network topology, module structure, data flows,
  permission model, security invariants

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

- [Settings Reference](SETTINGS.md) — all environment variables,
  defaults, and configuration classes
- [Infrastructure Reference](INFRASTRUCTURE.md) — Docker Compose
  services, ports, volumes, and integration test stack
- [Entity Relationship Diagram](ERD.md) — database schema
  (Feature 1.2 tables; updated each feature)

### History

- [Development Journal](HISTORY.md) — running log of the development
  process, decisions, and lessons learned

### Legal Framework

- [Third-Party Licenses](../LICENSING.md) — component
  license inventory and compatibility analysis

*Coming soon — jurisdiction-specific discovery rules,
compliance references, and domain glossary.*
