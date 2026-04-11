"""Celery application — broker connection and base configuration.

The celery command discovers this module via ``celery -A app.workers``.
Task modules are auto-discovered from ``app.workers.tasks``.
"""

from celery import Celery  # type: ignore[import-untyped]
from celery.signals import beat_init, worker_init  # type: ignore[import-untyped]

from app.core.config import settings

celery_app = Celery("gideon")

if settings.celery.broker_url is None:
    msg = (
        "Celery broker_url is None. Set GIDEON_CELERY_BROKER_URL or "
        "configure GIDEON_REDIS_* fields and instantiate via Settings."
    )
    raise ValueError(msg)

conf = settings.celery.model_dump()
# Celery calls it task_time_limit; we use task_hard_time_limit for clarity
# in env vars so it's not confused with task_soft_time_limit.
conf["task_time_limit"] = conf.pop("task_hard_time_limit", conf.get("task_time_limit"))
celery_app.conf.update(**conf)

celery_app.autodiscover_tasks(["app.workers"])


# --- Observability (Feature 2.7) ---
# Initialise OTel providers and wire the CeleryInstrumentor when a worker
# or beat process actually starts — not at module import time.  This avoids
# polluting global OTel state when tests merely import celery_app.


def _init_otel() -> None:
    """Set up OTel tracing and Celery instrumentation."""
    from app.core.telemetry import configure_celery_instrumentation, setup_telemetry

    setup_telemetry(settings)
    configure_celery_instrumentation(settings)


@worker_init.connect  # type: ignore[untyped-decorator]
def _on_worker_init(**_kwargs: object) -> None:
    _init_otel()


@beat_init.connect  # type: ignore[untyped-decorator]
def _on_beat_init(**_kwargs: object) -> None:
    _init_otel()
