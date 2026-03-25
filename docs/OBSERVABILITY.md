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

| Span name | Module | Purpose |
| --- | --- | --- |
| `permissions.build_qdrant_filter` | `core/permissions.py` | Vector query access control |
| `permissions.check_role` | `core/permissions.py` | Role enforcement on endpoints |
| `permissions.check_matter_access` | `core/permissions.py` | Matter-level access verification |
| `broker.submit` | `workers/broker.py` | Task submission (`messaging.destination.name`, `messaging.message.id`) |
| `broker.get_status` | `workers/broker.py` | Task status query (`messaging.message.id`, `messaging.operation.name`) |
| `broker.revoke` | `workers/broker.py` | Task cancellation (`messaging.message.id`, `messaging.operation.terminate`) |

### Metrics

Metrics are counters, histograms, and gauges exported via OTel's
`PeriodicExportingMetricReader` (60-second interval).

All metric instruments are defined in `backend/app/core/metrics.py`:

| Metric | Type | Description |
| --- | --- | --- |
| `opencase.auth.login_attempts` | Counter | Login attempts by result (success/failure/locked) |
| `opencase.auth.mfa_challenges` | Counter | MFA TOTP challenge outcomes |
| `opencase.auth.token_refresh_attempts` | Counter | Token refresh attempts |
| `opencase.auth.active_sessions` | UpDownCounter | Active sessions (issued minus logouts) |
| `opencase.rbac.access_denied` | Counter | RBAC denials by reason (role/matter) and role |
| `opencase.tasks.submitted` | Counter | Tasks submitted (API + broker level) |
| `opencase.tasks.cancelled` | Counter | Tasks cancelled |
| `opencase.tasks.status_queried` | Counter | Task status queries via broker |

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
