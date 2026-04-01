# OpenCase — Observability

All observability data stays on-premise. No telemetry leaves the host.

---

## Strategy

OpenCase uses **OpenTelemetry** (OTel) to collect all three signals — traces,
metrics, and logs — from the FastAPI backend, Celery worker, and Celery Beat
processes. The OTLP backend is
**Grafana otel-lgtm**, a single Docker container that bundles:

| Component | Signal | Purpose |
| --- | --- | --- |
| OTel Collector | All | Receives OTLP HTTP/gRPC, routes to backends |
| Tempo | Traces | Distributed trace storage and search |
| Prometheus | Metrics | Time-series metrics storage and query |
| Loki | Logs | Structured log aggregation and search |
| Grafana | UI | Unified dashboard for all three signals |

The Grafana UI is available at `http://localhost:3001` with pre-configured
datasources for Tempo, Prometheus, and Loki out of the box.

---

## Signals

### Traces

Traces capture the full lifecycle of a request — from the FastAPI HTTP handler
through SQLAlchemy queries, RBAC permission checks, and (in future features)
RAG pipeline stages.

**Automatic instrumentation** (via OTel instrumentors):

- FastAPI HTTP requests → `GET /path`, `POST /path` spans
- SQLAlchemy queries → `SELECT`, `INSERT`, `UPDATE`, `DELETE` spans
- Celery tasks → `run`, `apply_async`, `delay` spans (worker + beat)

**Manual instrumentation** (via `opentelemetry.trace`):

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def ingest_document(doc):
    with tracer.start_as_current_span("ingest_document") as span:
        span.set_attribute("document.id", str(doc.id))
```

Current manually instrumented spans:

#### RBAC / Auth

| Span name | Module | Purpose |
| --- | --- | --- |
| `permissions.build_qdrant_filter` | `core/permissions.py` | Vector query access control |
| `permissions.check_role` | `core/permissions.py` | Role enforcement on endpoints |
| `permissions.check_matter_access` | `core/permissions.py` | Matter-level access verification |
| `auth.login` | `api/auth.py` | Login flow |
| `auth.mfa_verify` | `api/auth.py` | MFA TOTP verification |
| `auth.mfa_setup` | `api/auth.py` | MFA provisioning |
| `auth.mfa_confirm` | `api/auth.py` | MFA confirmation |
| `auth.mfa_disable` | `api/auth.py` | MFA removal |
| `auth.token_refresh` | `api/auth.py` | JWT token refresh |
| `auth.logout` | `api/auth.py` | Session teardown |

#### Task Broker

| Span name | Module | Purpose |
| --- | --- | --- |
| `broker.submit` | `workers/broker.py` | Task submission (`messaging.destination.name`, `messaging.message.id`) |
| `broker.get_status` | `workers/broker.py` | Task status query (`messaging.message.id`, `messaging.operation.name`) |
| `broker.revoke` | `workers/broker.py` | Task cancellation (`messaging.message.id`, `celery.revoke.terminate`) |

#### Celery Tasks

| Span name | Module | Purpose |
| --- | --- | --- |
| `extract_document` | `workers/tasks/extract_document.py` | Parent span for standalone extraction task |
| `extraction.s3_download` | `workers/tasks/extract_document.py` | S3 download within extraction task |
| `ingest_document` | `workers/tasks/ingest_document.py` | Parent span for full ingestion pipeline |
| `ingestion.s3_download` | `workers/tasks/ingest_document.py` | S3 download of original document |
| `ingestion.s3_upload` | `workers/tasks/ingest_document.py` | S3 upload of extracted.json / chunks.json |
| `ingestion.db_lookup` | `workers/tasks/ingest_document.py` | Document + Matter metadata fetch |
| `ingestion.chunk` | `workers/tasks/ingest_document.py` | Chunking stage of ingestion |
| `ingestion.embed_upsert` | `workers/tasks/ingest_document.py` | Embedding + Qdrant upsert stage |
| `chunk_document` | `workers/tasks/chunk_document.py` | Parent span for standalone chunking task |
| `embed_chunks` | `workers/tasks/embed_chunks.py` | Parent span for standalone embed+upsert task |

#### Service-Level Spans (with metrics)

| Span name | Module | Attributes |
| --- | --- | --- |
| `extraction.extract_text` | `extraction/tika.py` | `extraction.filename`, `extraction.size_bytes`, `extraction.content_type`, `extraction.text_length`, `extraction.ocr_applied`, `extraction.detected_content_type`, `extraction.language` |
| `chunking.chunk_text` | `chunking/service.py` | `chunking.document_id`, `chunking.text_length`, `chunking.chunk_count`, `chunking.strategy` |
| `embedding.embed_chunks` | `embedding/service.py` | `embedding.chunk_count`, `embedding.model`, `embedding.batch_size`, `embedding.result_count`, `embedding.batch_count` |
| `vectorstore.upsert_vectors` | `vectorstore/service.py` | `vectorstore.collection`, `vectorstore.point_count`, `vectorstore.batch_count` |
| `vectorstore.delete_by_document` | `vectorstore/service.py` | `vectorstore.collection`, `vectorstore.document_id`, `vectorstore.deleted_count` |

### Metrics

Metrics are counters, histograms, and gauges exported via OTel's
`PeriodicExportingMetricReader` (60-second interval).

All metric instruments are defined in `backend/app/core/metrics.py`:

#### Auth

| Metric | Type | Attrs | Description |
| --- | --- | --- | --- |
| `opencase.auth.login_attempts` | Counter | `result` | Login attempts (success/failure/locked) |
| `opencase.auth.mfa_challenges` | Counter | `result` | MFA TOTP challenge outcomes |
| `opencase.auth.token_refresh_attempts` | Counter | | Token refresh attempts |
| `opencase.auth.active_sessions` | UpDownCounter | | Active sessions (issued minus logouts) |

#### RBAC

| Metric | Type | Attrs | Description |
| --- | --- | --- | --- |
| `opencase.rbac.access_denied` | Counter | `reason`, `role` | RBAC denials |

#### Entity Management

| Metric | Type | Attrs | Description |
| --- | --- | --- | --- |
| `opencase.users.created` | Counter | | Users created |
| `opencase.users.updated` | Counter | | Users updated |
| `opencase.matters.created` | Counter | | Matters created |
| `opencase.matters.updated` | Counter | | Matters updated |
| `opencase.matter_access.granted` | Counter | | Matter access grants |
| `opencase.matter_access.revoked` | Counter | | Matter access revocations |

#### Documents

| Metric | Type | Attrs | Description |
| --- | --- | --- | --- |
| `opencase.documents.created` | Counter | | Documents created |
| `opencase.documents.duplicates_rejected` | Counter | | Duplicate upload rejections |

#### Prompts

| Metric | Type | Attrs | Description |
| --- | --- | --- | --- |
| `opencase.prompts.created` | Counter | | Prompts submitted |

#### Tasks

| Metric | Type | Attrs | Description |
| --- | --- | --- | --- |
| `opencase.tasks.submitted` | Counter | `task_name` | Tasks submitted via API |
| `opencase.tasks.cancelled` | Counter | | Tasks cancelled |
| `opencase.tasks.status_queried` | Counter | `task_state` | Task status queries via broker |

#### Extraction

| Metric | Type | Attrs | Description |
| --- | --- | --- | --- |
| `opencase.extraction.completed` | Counter | `content_type`, `ocr_applied` | Successful extractions |
| `opencase.extraction.failed` | Counter | `content_type`, `error_type` | Failed extractions |
| `opencase.extraction.duration_seconds` | Histogram (s) | `content_type`, `ocr_applied` | Extraction latency |
| `opencase.extraction.document_size_bytes` | Histogram (By) | `content_type`, `ocr_applied` | Input document size |
| `opencase.extraction.text_length_chars` | Histogram ({char}) | `content_type`, `ocr_applied` | Extracted text length |

#### Chunking

| Metric | Type | Attrs | Description |
| --- | --- | --- | --- |
| `opencase.chunking.completed` | Counter | `strategy` | Successful chunk operations |
| `opencase.chunking.failed` | Counter | `error_type` | Failed chunk operations |
| `opencase.chunking.duration_seconds` | Histogram (s) | `strategy` | Chunking latency |
| `opencase.chunking.text_length_chars` | Histogram ({char}) | `strategy` | Input text length |
| `opencase.chunking.chunks_produced` | Histogram ({chunk}) | `strategy` | Chunks produced per document |

#### Embedding

| Metric | Type | Attrs | Description |
| --- | --- | --- | --- |
| `opencase.embedding.completed` | Counter | `model` | Successful embedding operations |
| `opencase.embedding.failed` | Counter | `model`, `error_type` | Failed embedding operations |
| `opencase.embedding.duration_seconds` | Histogram (s) | `model` | Embedding latency |
| `opencase.embedding.chunks_processed` | Histogram ({chunk}) | `model` | Chunks embedded per call |
| `opencase.embedding.batch_count` | Histogram ({batch}) | `model` | Batches per embedding call |

#### Vectorstore

| Metric | Type | Attrs | Description |
| --- | --- | --- | --- |
| `opencase.vectorstore.upsert.completed` | Counter | `collection` | Successful upserts |
| `opencase.vectorstore.upsert.failed` | Counter | `collection`, `error_type` | Failed upserts |
| `opencase.vectorstore.upsert.duration_seconds` | Histogram (s) | `collection` | Upsert latency |
| `opencase.vectorstore.upsert.points` | Histogram ({point}) | `collection` | Points upserted per call |
| `opencase.vectorstore.delete.completed` | Counter | `collection` | Successful deletes |
| `opencase.vectorstore.delete.duration_seconds` | Histogram (s) | `collection` | Delete latency |

New features should add their metrics to `metrics.py` following the
`opencase.<domain>.<metric_name>` naming convention.

### Logs

Python's standard `logging` module is bridged to the OTLP backend via
`LoggingHandler`. When `exporter=otlp`, all application logs are sent to
Loki alongside their normal stdout output. No code changes are needed —
any module using `logging.getLogger(__name__)` participates automatically.

Logs are correlated with traces via OTel context propagation, so you can
jump from a trace span to its associated log entries in Grafana.

---

## Configuration

All settings use the `OPENCASE_OTEL_` prefix:

| Variable | Default | Description |
| --- | --- | --- |
| `OPENCASE_OTEL_ENABLED` | `false` | Enable all OTel instrumentation |
| `OPENCASE_OTEL_EXPORTER` | `console` | `console` (stdout) or `otlp` (Grafana otel-lgtm) |
| `OPENCASE_OTEL_ENDPOINT` | `http://grafana:4318` | OTLP HTTP endpoint |
| `OPENCASE_OTEL_SERVICE_NAME` | `opencase-api` | Resource tag on all signals |
| `OPENCASE_OTEL_SAMPLE_RATE` | `1.0` | Trace sampling rate (0.0–1.0) |

See [SETTINGS.md](SETTINGS.md) for the full settings reference.

---

## Architecture

```text
FastAPI (opencase-api)        ─┐
Celery Worker (opencase-worker) ├── traces  ──→ OTLP HTTP ──→ OTel Collector ──→ Tempo
Celery Beat (opencase-beat)   ─┘  metrics ──→ OTLP HTTP ──→ OTel Collector ──→ Prometheus
                                  logs    ──→ OTLP HTTP ──→ OTel Collector ──→ Loki
                                                                                  │
                                                                             Grafana UI
                                                                           localhost:3001
```

The `grafana/otel-lgtm` image runs all five components (Collector, Tempo,
Prometheus, Loki, Grafana) in a single container with zero configuration.

---

## Instrumentation Pattern

Every feature implementation should include observability:

1. **Traces** — wrap key operations in spans with meaningful attributes
2. **Metrics** — add counters/histograms to `core/metrics.py`
3. **Logs** — use `logging.getLogger(__name__)` (automatic via bridge)

Example from `core/permissions.py`:

```python
from opentelemetry import trace
from app.core.metrics import access_denied

tracer = trace.get_tracer(__name__)

async def build_qdrant_filter(user, matter_id, db):
    with tracer.start_as_current_span(
        "permissions.build_qdrant_filter",
        attributes={"user.id": str(user.id), "matter.id": str(matter_id)},
    ):
        # ... permission logic ...
        if access_row is None:
            access_denied.add(1, {"reason": "matter", "role": user.role.value})
            raise HTTPException(status_code=404)
```

---

## Key Files

| File | Purpose |
| --- | --- |
| `backend/app/core/telemetry.py` | OTel setup — exporter factories, provider init, instrumentor wiring |
| `backend/app/core/metrics.py` | Metric instrument definitions |
| `backend/app/core/logging.py` | Python logging configuration |
| `backend/app/core/config.py` | `OtelSettings` class |
| `infrastructure/docker-compose.yml` | Grafana otel-lgtm service definition |

---

## Docker

The Grafana otel-lgtm container:

| Port | Protocol | Purpose |
| --- | --- | --- |
| `3001` | HTTP | Grafana UI (mapped from container port 3000) |
| `4317` | gRPC | OTLP gRPC receiver |
| `4318` | HTTP | OTLP HTTP receiver |

Volume: `grafana-data` persists dashboards, trace data, metrics, and logs.

See [INFRASTRUCTURE.md](INFRASTRUCTURE.md) for the full service reference.

---

## Grafana Datasources

The otel-lgtm image auto-provisions these datasources:

| Datasource | Type | Query language |
| --- | --- | --- |
| Tempo | Traces | TraceQL |
| Prometheus | Metrics | PromQL |
| Loki | Logs | LogQL |

All three are available in Grafana's Explore view immediately after startup.
