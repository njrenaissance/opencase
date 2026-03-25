"""Celery task modules — imported by autodiscover_tasks."""

from app.workers.tasks.ping import ping  # noqa: F401
