"""Task registry — maps user-facing task names to Celery task names.

Only tasks listed here can be submitted via the API. Add new entries as
tasks are implemented (ingestion, deadline monitor, etc.).
"""

TASK_REGISTRY: dict[str, str] = {
    "ping": "opencase.ping",
    "sleep": "opencase.sleep",
    "ingest_document": "opencase.ingest_document",
    "extract_document": "opencase.extract_document",
    "chunk_document": "opencase.chunk_document",
}
