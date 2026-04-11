"""Task registry — maps user-facing task names to Celery task names.

Only tasks listed here can be submitted via the API. Add new entries as
tasks are implemented (ingestion, deadline monitor, etc.).
"""

TASK_REGISTRY: dict[str, str] = {
    "ping": "gideon.ping",
    "sleep": "gideon.sleep",
    "ingest_document": "gideon.ingest_document",
    "extract_document": "gideon.extract_document",
    "chunk_document": "gideon.chunk_document",
    "embed_chunks": "gideon.embed_chunks",
}
