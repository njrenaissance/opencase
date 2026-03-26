"""Long-running test task for monitoring and observability verification."""

import time

from celery import shared_task  # type: ignore[import-untyped]


@shared_task(name="opencase.sleep")  # type: ignore[untyped-decorator]
def sleep_task(seconds: int = 10) -> str:
    """Sleep for the given duration and return a summary string."""
    time.sleep(seconds)
    return f"slept {seconds}s"
