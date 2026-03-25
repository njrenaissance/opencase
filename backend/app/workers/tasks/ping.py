"""Health-check task for verifying worker connectivity."""

from celery import shared_task  # type: ignore[import-untyped]


@shared_task(name="opencase.ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    """Return 'pong' — used by integration tests and health checks."""
    return "pong"
