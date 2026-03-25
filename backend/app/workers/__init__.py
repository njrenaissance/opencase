"""Celery application — broker connection and base configuration.

The celery command discovers this module via ``celery -A app.workers``.
Task modules are auto-discovered from ``app.workers.tasks``.
"""

from celery import Celery  # type: ignore[import-untyped]

from app.core.config import settings

celery_app = Celery("opencase")

conf = settings.celery.model_dump()
# Celery calls it task_time_limit; we use task_hard_time_limit for clarity in env vars.
conf["task_time_limit"] = conf.pop("task_hard_time_limit")
celery_app.conf.update(**conf)

celery_app.autodiscover_tasks(["app.workers"])
