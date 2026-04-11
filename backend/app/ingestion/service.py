"""Ingestion workflow — submits documents for background extraction.

After a document is uploaded and stored in S3, this service submits an
``ingest_document`` Celery task that runs the extraction pipeline
(Tika text extraction → persist extracted.json to S3).
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates the document ingestion pipeline.

    Submits an ``ingest_document`` Celery task that downloads from S3,
    extracts text via Tika, and persists the result alongside the original.
    """

    async def process_document(self, document_id: uuid.UUID, s3_key: str) -> None:
        """Kick off ingestion for a newly uploaded document.

        Args:
            document_id: The document's primary key.
            s3_key: The S3 object key where the original file is stored.
        """
        from app.workers import celery_app

        celery_app.send_task(
            "gideon.ingest_document",
            args=[str(document_id), s3_key],
        )
        logger.info(
            "Submitted ingest_document task: document_id=%s s3_key=%s",
            document_id,
            s3_key,
        )
