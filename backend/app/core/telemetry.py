"""OpenTelemetry setup for on-premise observability.

All telemetry data stays on-premise. No data leaves the host.

The OTLP backend is Grafana's otel-lgtm stack (OTel Collector + Tempo +
Prometheus + Loki + Grafana UI) running as a single Docker container.
All three OTel signals — traces, metrics, and logs — are collected.

Usage — Traces and Spans
~~~~~~~~~~~~~~~~~~~~~~~~

A **trace** is a complete request lifecycle (e.g. an API call from start
to finish). A **span** is a unit of work within a trace (e.g. a database
query, an LLM call). Spans nest to form a tree.

To add custom spans in any module::

    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)

    async def ingest_document(doc):
        with tracer.start_as_current_span("ingest_document") as span:
            span.set_attribute("document.id", doc.id)
            span.set_attribute("document.type", doc.content_type)

            with tracer.start_as_current_span("extract_text"):
                text = await extract(doc)

            with tracer.start_as_current_span("embed_chunks"):
                chunks = await embed(text)

            span.set_attribute("document.chunk_count", len(chunks))

FastAPI requests are automatically traced via FastAPIInstrumentor
(configured in main.py).

Usage — Metrics
~~~~~~~~~~~~~~~

Use the module-level ``meter`` to create counters, histograms, etc.::

    from app.core.telemetry import meter

    doc_counter = meter.create_counter(
        "gideon.documents.ingested",
        description="Number of documents ingested",
    )
    doc_counter.add(1, {"matter_id": matter.id})

Usage — Logs
~~~~~~~~~~~~

Application logs are exported to the OTLP backend via
``OTLPLogExporter`` when ``exporter=otlp``. Python's standard
``logging`` module is bridged automatically — no code changes
needed beyond the existing ``logging.getLogger(__name__)`` pattern.
"""

import logging
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    MetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from app.core.config import Settings

if TYPE_CHECKING:
    from fastapi import FastAPI
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None
_log_provider: "LoggerProvider | None" = None
_otel_resource: "Resource | None" = None

def get_meter() -> metrics.Meter:
    """Get the global meter, initializing on first call after setup_telemetry()."""
    global _meter  # noqa: PLW0603
    if _meter is None:
        _meter = metrics.get_meter("gideon")
    return _meter

_METRIC_EXPORT_INTERVAL_MS = 60000

# Lazily initialized after setup_telemetry() sets the MeterProvider.
# Accessing meter before setup_telemetry() returns None.
_meter: "metrics.Meter | None" = None


def _create_span_exporter(settings: Settings) -> SpanExporter:
    """Factory: return the configured span exporter.

    Lazy-imports backend-specific packages so the console path never
    requires the OTLP package to be installed.
    """
    if settings.otel.exporter == "otlp":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        endpoint = f"{settings.otel.endpoint}/v1/traces"
        logger.debug("Span exporter: otlp → %s", endpoint)
        return OTLPSpanExporter(endpoint=endpoint)

    # Default: console
    logger.debug("Span exporter: console")
    return ConsoleSpanExporter()


def _create_metric_exporter(settings: Settings) -> MetricExporter:
    """Factory: return the configured metric exporter."""
    if settings.otel.exporter == "otlp":
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )

        endpoint = f"{settings.otel.endpoint}/v1/metrics"
        logger.debug("Metric exporter: otlp → %s", endpoint)
        return OTLPMetricExporter(endpoint=endpoint)

    # Default: console
    logger.debug("Metric exporter: console")
    return ConsoleMetricExporter()


def _setup_log_exporter(settings: Settings, resource: Resource) -> None:
    """Wire the OTel log bridge so Python logging flows to the OTLP backend.

    Only activates when ``exporter=otlp``. Console mode relies on the
    existing ``logging.StreamHandler`` configured in ``logging.py``.
    """
    global _log_provider  # noqa: PLW0603

    if settings.otel.exporter != "otlp":
        return

    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import (
        OTLPLogExporter,
    )
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    endpoint = f"{settings.otel.endpoint}/v1/logs"
    logger.debug("Log exporter: otlp → %s", endpoint)

    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint))
    )
    set_logger_provider(log_provider)
    _log_provider = log_provider

    # Attach an OTel logging handler to the root logger so all app logs
    # are forwarded to the OTLP backend alongside stdout.
    otel_handler = LoggingHandler(level=logging.NOTSET, logger_provider=log_provider)
    logging.getLogger().addHandler(otel_handler)

    logger.debug("OTel log bridge wired")


def setup_telemetry(settings: Settings) -> TracerProvider | None:
    """Configure OpenTelemetry tracing, metrics, and logging.

    Returns the TracerProvider if enabled, None otherwise.
    Idempotent: repeated calls return the cached provider.
    """
    # Global state caches the OTel providers and resource for reuse across
    # the application lifetime (idempotent initialization).
    global _tracer_provider, _otel_resource  # noqa: PLW0603

    if not settings.otel.enabled:
        logger.info("OpenTelemetry disabled")
        return None

    if _tracer_provider is not None:
        return _tracer_provider

    resource = Resource.create(
        {
            "service.name": settings.otel.service_name,
            "service.version": settings.app_version,
        }
    )
    _otel_resource = resource
    logger.debug(
        "OTel resource created: service=%s version=%s",
        settings.otel.service_name,
        settings.app_version,
    )

    # Tracing
    sampler = TraceIdRatioBased(settings.otel.sample_rate)
    provider = TracerProvider(resource=resource, sampler=sampler)
    logger.debug("TracerProvider created: sample_rate=%s", settings.otel.sample_rate)
    # TODO: switch to BatchSpanProcessor for non-console exporters once
    # integration tests are updated to account for async export timing.
    provider.add_span_processor(SimpleSpanProcessor(_create_span_exporter(settings)))
    trace.set_tracer_provider(provider)
    _tracer_provider = provider

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        _create_metric_exporter(settings),
        export_interval_millis=_METRIC_EXPORT_INTERVAL_MS,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    logger.debug(
        "MeterProvider created: interval=%ds",
        _METRIC_EXPORT_INTERVAL_MS // 1000,
    )

    # Logs
    _setup_log_exporter(settings, resource)

    logger.info(
        "OpenTelemetry enabled: exporter=%s, service=%s",
        settings.otel.exporter,
        settings.otel.service_name,
    )
    return provider


def configure_celery_instrumentation(settings: Settings) -> None:
    """Wire the OTel CeleryInstrumentor for worker and beat processes.

    Called from ``app.workers.__init__`` after ``setup_telemetry()``.
    Separate from :func:`configure_instrumentation` because that function
    requires a FastAPI app and imports ``app.db.session`` — neither of which
    exists in worker context.
    """
    if not settings.otel.enabled:
        logger.debug("OTel disabled — skipping Celery instrumentation")
        return

    from opentelemetry.instrumentation.celery import CeleryInstrumentor

    instrumentor = CeleryInstrumentor()
    if not instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.instrument()
        logger.debug("OTel instrumentor wired: Celery")


def reattach_log_handler(settings: Settings) -> None:
    """Re-attach the OTel log bridge in a forked worker process.

    Called via worker_process_init signal after Celery forks a pool child.
    The fork inherits the parent's logging handler chain, but the HTTP
    connection pool inside OTLPLogExporter is invalid post-fork — the socket
    is shared and breaks. This function shuts down the stale provider,
    removes inherited handlers, creates a fresh LoggerProvider with
    SimpleLogRecordProcessor (to avoid background thread deadlock post-fork),
    and re-attaches the bridge.

    Safe to call multiple times (idempotent).
    """
    # Global state is necessary for multi-process coordination: the parent process
    # initializes OTel, then child processes call this function to re-init the log
    # bridge (because fork invalidates the HTTP connection pool).
    global _log_provider, _otel_resource  # noqa: PLW0603

    if not settings.otel.enabled or settings.otel.exporter != "otlp":
        return

    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import (
        OTLPLogExporter,
    )
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor

    # Shut down stale provider (inherited from parent). The background thread
    # and HTTP connection pool are in an invalid state post-fork.
    if _log_provider is not None:
        try:
            _log_provider.shutdown()  # type: ignore[no-untyped-call]
        except Exception:
            logger.debug("Failed to shut down stale log provider", exc_info=True)
        _log_provider = None

    # Remove stale handlers from root logger (inherited from parent before fork).
    root_logger = logging.getLogger()
    stale_handlers = [h for h in root_logger.handlers if isinstance(h, LoggingHandler)]
    for h in stale_handlers:
        root_logger.removeHandler(h)

    # Reuse the resource from the parent setup_telemetry call for consistency.
    resource = _otel_resource
    if resource is None:
        resource = Resource.create(
            {
                "service.name": settings.otel.service_name,
                "service.version": settings.app_version,
            }
        )

    endpoint = f"{settings.otel.endpoint}/v1/logs"
    logger.debug("Re-attaching OTel log bridge in forked process → %s", endpoint)

    # Use SimpleLogRecordProcessor in the child to avoid spawning a background
    # thread that could deadlock (BatchLogRecordProcessor starts a daemon thread,
    # but post-fork the thread state may be invalid). Task durations are short,
    # so blocking on export is acceptable.
    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(
        SimpleLogRecordProcessor(OTLPLogExporter(endpoint=endpoint))
    )
    set_logger_provider(log_provider)
    _log_provider = log_provider

    # Attach fresh handler to root logger.
    otel_handler = LoggingHandler(level=logging.NOTSET, logger_provider=log_provider)
    root_logger.addHandler(otel_handler)

    logger.debug("OTel log bridge re-attached in forked process")


def configure_instrumentation(app: "FastAPI", settings: Settings) -> None:
    """Wire OTel instrumentors for FastAPI and SQLAlchemy.

    Called from main.py after the FastAPI app and DB engine are both created.
    Lazy imports keep telemetry.py free of circular dependencies at module level.
    ``app`` is passed in rather than imported — telemetry.py never imports main.py.
    """
    if not settings.otel.enabled:
        logger.debug("OTel disabled — skipping instrumentation")
        return

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    from app.db.session import engine

    FastAPIInstrumentor.instrument_app(app)

    # AsyncEngine wraps a sync engine; SQLAlchemyInstrumentor requires the sync one.
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)

    logger.debug("OTel instrumentors wired: FastAPI + SQLAlchemy")
