"""Unit tests for OpenTelemetry telemetry setup."""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from app.core import telemetry
from app.core.config import OtelSettings, Settings


@pytest.fixture(autouse=True)
def _reset_telemetry():
    """Reset module-level and global OTel state between tests."""
    telemetry._tracer_provider = None
    # Reset the global provider lock so tests can set it again.
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    yield
    telemetry._tracer_provider = None
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False


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
        def instrument(self):
            called["instrument"] = True

    monkeypatch.setattr(
        "opentelemetry.instrumentation.celery.CeleryInstrumentor",
        _FakeInstrumentor,
    )
    telemetry.configure_celery_instrumentation(_make_settings(enabled=True))
    assert called["instrument"]
