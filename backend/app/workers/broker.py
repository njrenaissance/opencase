"""TaskBroker — thin abstraction over Celery for submit, status, and revoke.

Keeps the FastAPI layer decoupled from Celery internals so the background
job backend can be swapped in the future without touching the API router.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from celery import Celery  # type: ignore[import-untyped]
from opentelemetry import trace
from opentelemetry.trace import SpanKind, StatusCode

from app.core.metrics import tasks_cancelled, tasks_status_queried, tasks_submitted
from app.workers import celery_app

tracer = trace.get_tracer(__name__)


@dataclass(frozen=True)
class TaskStatusResult:
    """Snapshot of a task's current state from the result backend."""

    state: str
    result: Any | None
    date_done: datetime | None
    traceback: str | None


class TaskBroker:
    """Wraps Celery send_task / AsyncResult / control.revoke."""

    def __init__(self, celery: Celery) -> None:
        self._celery = celery

    def submit(
        self, celery_task_name: str, args: list[Any], kwargs: dict[str, Any]
    ) -> str:
        """Submit a task and return its ID."""
        with tracer.start_as_current_span(
            "broker.submit", kind=SpanKind.PRODUCER
        ) as span:
            span.set_attribute("messaging.destination.name", celery_task_name)
            try:
                result = self._celery.send_task(
                    celery_task_name, args=args, kwargs=kwargs
                )
                task_id = str(result.id)
                span.set_attribute("messaging.message.id", task_id)
                tasks_submitted.add(1, {"task_name": celery_task_name})
                return task_id
            except Exception as exc:
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise

    def get_status(self, task_id: str) -> TaskStatusResult:
        """Query the result backend for live task state."""
        with tracer.start_as_current_span("broker.get_status") as span:
            span.set_attribute("messaging.message.id", task_id)
            try:
                r = self._celery.AsyncResult(task_id)
                status = TaskStatusResult(
                    state=r.state,
                    result=r.result,
                    date_done=getattr(r, "date_done", None),
                    traceback=r.traceback,
                )
                span.set_attribute("messaging.operation.name", status.state)
                tasks_status_queried.add(1, {"task_state": status.state})
                return status
            except Exception as exc:
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise

    def revoke(self, task_id: str, *, terminate: bool = False) -> None:
        """Revoke (cancel) a pending or running task."""
        with tracer.start_as_current_span("broker.revoke") as span:
            span.set_attribute("messaging.message.id", task_id)
            span.set_attribute("celery.revoke.terminate", terminate)
            try:
                self._celery.control.revoke(task_id, terminate=terminate)
                tasks_cancelled.add(1)
            except Exception as exc:
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise


# Singleton — shared across all requests.
_broker = TaskBroker(celery_app)


def get_task_broker() -> TaskBroker:
    """FastAPI dependency returning the TaskBroker singleton."""
    return _broker
