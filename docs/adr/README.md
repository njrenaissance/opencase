# Architecture Decision Records (ADRs)

This directory contains architectural decisions for Gideon. Each ADR documents a significant design choice, the rationale, alternatives considered, and consequences.

## Format

Each ADR follows the standard template:
- **Status**: Proposed, Accepted, Deprecated, Superseded
- **Context**: The problem and constraints
- **Decision**: What we decided and why
- **Consequences**: Positive and negative outcomes
- **Alternatives**: What we considered but rejected

## Index

| # | Title | Status | Date | Topic |
|---|-------|--------|------|-------|
| [0001](0001-recursive-character-chunking-strategy.md) | Recursive Character Chunking Strategy | Accepted | 2026-05-05 | Chunking |

## Pending Decisions

These are decisions that need documentation:

- **Caption Parsing**: Extract metadata (case number, parties, court) from document headers for filtering
- **Hybrid Search**: Combine metadata filter + semantic search for domain-specific queries
- **Batch Size Tuning**: Request size limits for Ollama embedding API
- **Celery Subtask Chain**: Refactor ingestion into restartable subtasks with granular state tracking
- **Permission Model**: How documents are scoped by firm/matter and enforced in queries

## How to Propose a New ADR

1. Create a new file: `000N-short-title.md` (increment the number)
2. Use the template structure (see 0001 for reference)
3. Submit as a pull request for team review
4. Update this README once accepted

## Related Documentation

- [Architecture Overview](../ARCHITECTURE.md)
- [Chunking Configuration](../settings.md#chunking)
- [Ingestion Pipeline](../TASKS.md)
