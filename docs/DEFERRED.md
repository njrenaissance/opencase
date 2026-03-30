# OpenCase Deferred Features

Features deferred to V1.1 or later.

| ID | Feature | Status |
| --- | --- | --- |
| **10.0** | **Brady/Giglio Tracker** | **Pending** |
| 10.1 | DB models + migration (disclosure_checklist, cpl_3030_events, motions, coc_tracking tables) | Pending |
| 10.2 | Tracker API endpoints (read-only — clocks, checklist, CoC status, motions, 30.30 events) | Pending |
| 10.3 | CPL 245 disclosure clocks | Pending |
| 10.4 | CPL 245.20(1) disclosure checklist (category tracking — what's received, what's outstanding) | Pending |
| 10.5 | Certificate of Compliance tracking (prosecution certification, defense challenges) | Pending |
| 10.6 | CPL 30.30 speedy trial clock (chargeable time, tolling events) | Pending |
| 10.7 | CPL 30.30 event ledger (dedicated table — every clock-affecting event with source document, chargeable party, running total) | Pending |
| 10.8 | Motion tracking (filed motions that affect clock tolling) | Pending |
| 10.9 | Brady/Giglio classification (AI-driven, updates disclosure checklist) | Pending |
| 10.10 | Deadline alerts (Celery Beat, approaching deadlines and overdue items) | Pending |
| 10.11 | Export API (CSV/JSON — disclosure checklist, clock status, classifications for case management import) | Pending |
| 10.12 | Configuration + env vars (TrackerSettings) | Pending |
| 10.13 | Observability (tracker spans/metrics) | Pending |
| **11.0** | **Witness Index** | **Pending** |
| 11.1 | DB models + migration (witnesses, witness-document links, testimony status, aliases) | Pending |
| 11.2 | Witness API endpoints (read-only — list witnesses, view linked documents, testimony status) | Pending |
| 11.3 | Entity extraction Celery task (AI-driven name extraction from ingested documents) | Pending |
| 11.4 | Witness deduplication (resolve name variants — "Officer J. Smith" / "Det. Smith") | Pending |
| 11.5 | Witness-document linking | Pending |
| 11.6 | Giglio flagging (mark witnesses with impeachment material) | Pending |
| 11.7 | Jencks material gating (filter prior statements until has_testified = true) | Pending |
| 11.8 | Configuration + env vars (WitnessIndexSettings) | Pending |
| 11.9 | Observability (entity extraction spans/metrics) | Pending |
| **12.0** | **Legal Hold** | **Pending** |
| 12.1 | Hold model (matter-level and document-level holds in PostgreSQL) | Pending |
| 12.2 | Hold API (create, release, query hold status) | Pending |
| 12.3 | Enforcement hooks (block delete/modify on held documents in S3 and DB) | Pending |
| 12.4 | Hold audit trail (all hold/release actions logged to audit chain) | Pending |
| 12.5 | Configuration + env vars (HoldSettings) | Pending |
| 12.6 | Observability (hold enforcement spans/metrics) | Pending |
