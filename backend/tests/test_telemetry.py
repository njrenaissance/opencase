"""Unit tests for OpenTelemetry telemetry setup."""

import logging

import pytest
from opentelemetry import trace
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from app.core import telemetry
from app.core.config import OtelSettings, Settings


def _strip_otel_handlers() -> None:
    """Remove all OTel LoggingHandler instances from root logger."""
    root_logger = logging.getLogger()
    for h in [h for h in root_logger.handlers if isinstance(h, LoggingHandler)]:
        root_logger.removeHandler(h)


@pytest.fixture(autouse=True)
def _reset_telemetry():
    """Reset module-level and global OTel state between tests."""
    from opentelemetry._logs import set_logger_provider

    telemetry._tracer_provider = None
    telemetry._log_provider = None
    telemetry._otel_resource = None
    # Reset the global provider lock so tests can set it again.
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    # Reset the global logger provider so tests start fresh.
    set_logger_provider(None)
    _strip_otel_handlers()
    yield
    telemetry._tracer_provider = None
    telemetry._log_provider = None
    telemetry._otel_resource = None
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    set_logger_provider(None)
    _strip_otel_handlers()


def _make_settings(**otel_overrides) -> Settings:
    """Create Settings with OTel overrides."""
    otel = OtelSettings(**otel_overrides)
    return Settings(otel=otel)


def test_disabled_returns_none():
    result = telemetry.setup_telemetry(_make_settings(enabled=False))
    assert result is None


def test_disabled_does_not_set_global_provider():
    telemetry.setup_telemetry(_make_settings(enabled=False))
    provider = trace.get_tracer_provider()
    assert not isinstance(provider, TracerProvider)


def test_enabled_returns_tracer_provider():
    result = telemetry.setup_telemetry(_make_settings(enabled=True))
    assert isinstance(result, TracerProvider)


def test_resource_has_service_name():
    provider = telemetry.setup_telemetry(
        _make_settings(enabled=True, service_name="test-svc")
    )
    assert provider.resource.attributes["service.name"] == "test-svc"


def test_resource_has_service_version():
    provider = telemetry.setup_telemetry(_make_settings(enabled=True))
    assert "service.version" in provider.resource.attributes


def test_console_exporter_processor():
    provider = telemetry.setup_telemetry(_make_settings(enabled=True))
    processors = provider._active_span_processor._span_processors
    assert len(processors) == 1
    assert isinstance(processors[0], SimpleSpanProcessor)
    assert isinstance(processors[0].span_exporter, ConsoleSpanExporter)


def test_sampler_uses_configured_rate():
    provider = telemetry.setup_telemetry(_make_settings(enabled=True, sample_rate=0.5))
    assert isinstance(provider.sampler, TraceIdRatioBased)


def test_idempotent_returns_same_provider():
    s = _make_settings(enabled=True)
    p1 = telemetry.setup_telemetry(s)
    p2 = telemetry.setup_telemetry(s)
    assert p1 is p2


def test_sets_global_tracer_provider():
    telemetry.setup_telemetry(_make_settings(enabled=True))
    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider)


# ---------------------------------------------------------------------------
# configure_celery_instrumentation (Feature 2.7)
# ---------------------------------------------------------------------------


def test_celery_instrumentation_skipped_when_disabled():
    """No error when OTel is disabled — CeleryInstrumentor is never imported."""
    telemetry.configure_celery_instrumentation(_make_settings(enabled=False))


def test_celery_instrumentation_calls_instrumentor(monkeypatch):
    """CeleryInstrumentor().instrument() is called when OTel is enabled."""
    telemetry.setup_telemetry(_make_settings(enabled=True))

    called = {"instrument": False}

    class _FakeInstrumentor:
        is_instrumented_by_opentelemetry = False

        def instrument(self):
            called["instrument"] = True

    # Patch at the source — the lazy import inside
    # configure_celery_instrumentation reads from this path each call.
    monkeypatch.setattr(
        "opentelemetry.instrumentation.celery.CeleryInstrumentor",
        _FakeInstrumentor,
    )
    telemetry.configure_celery_instrumentation(_make_settings(enabled=True))
    assert called["instrument"]


# ---------------------------------------------------------------------------
# reattach_log_handler (Feature 2.7 — Celery worker log export)
# ---------------------------------------------------------------------------


def test_reattach_log_handler_skipped_when_disabled():
    """No error when OTel is disabled — no handler added."""
    telemetry.reattach_log_handler(_make_settings(enabled=False))
    root_logger = logging.getLogger()
    otel_handlers = [h for h in root_logger.handlers if isinstance(h, LoggingHandler)]
    assert len(otel_handlers) == 0


def test_reattach_log_handler_skipped_for_console_exporter():
    """No handler added when exporter=console."""
    telemetry.reattach_log_handler(_make_settings(enabled=True, exporter="console"))
    root_logger = logging.getLogger()
    otel_handlers = [h for h in root_logger.handlers if isinstance(h, LoggingHandler)]
    assert len(otel_handlers) == 0


@pytest.mark.integration
def test_reattach_log_handler_attaches_handler_to_root_logger():
    """After call with exporter=otlp, root logger has a LoggingHandler."""
    telemetry.reattach_log_handler(_make_settings(enabled=True, exporter="otlp"))
    root_logger = logging.getLogger()
    otel_handlers = [h for h in root_logger.handlers if isinstance(h, LoggingHandler)]
    assert len(otel_handlers) == 1


@pytest.mark.integration
def test_reattach_log_handler_removes_stale_handlers():
    """Calling twice results in exactly one LoggingHandler (no duplicates)."""
    telemetry.reattach_log_handler(_make_settings(enabled=True, exporter="otlp"))
    root_logger = logging.getLogger()
    first_call_handlers = [
        h for h in root_logger.handlers if isinstance(h, LoggingHandler)
    ]
    assert len(first_call_handlers) == 1

    telemetry.reattach_log_handler(_make_settings(enabled=True, exporter="otlp"))
    second_call_handlers = [
        h for h in root_logger.handlers if isinstance(h, LoggingHandler)
    ]
    assert len(second_call_handlers) == 1


@pytest.mark.integration
def test_setup_log_exporter_sets_logger_provider():
    """Verify setup_telemetry sets up a LoggerProvider when otlp is enabled."""
    telemetry.setup_telemetry(_make_settings(enabled=True, exporter="otlp"))
    log_provider = telemetry._log_provider
    assert log_provider is not None
    # Verify a logger provider is set globally (the SDK may cache/wrap it).
    from opentelemetry._logs import get_logger_provider

    global_provider = get_logger_provider()
    assert global_provider is not None
