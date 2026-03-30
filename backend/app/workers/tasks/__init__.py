"""Celery task modules.

autodiscover_tasks(["app.workers"]) imports this package. Since individual
task modules live in separate files (ping.py, etc.), they must be imported
here so their @shared_task decorators run and register with Celery.
"""

from app.workers.tasks.extract_document import extract_document  # noqa: F401
from app.workers.tasks.ingest_document import ingest_document  # noqa: F401
from app.workers.tasks.ping import ping  # noqa: F401
from app.workers.tasks.sleep import sleep_task  # noqa: F401
