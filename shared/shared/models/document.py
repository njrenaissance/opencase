"""Pydantic request/response models for document endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from shared.models.enums import Classification, DocumentSource, IngestionStatus

# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class DocumentSummary(BaseModel):
    """Lightweight document reference (for lists)."""

    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    source: DocumentSource
    classification: Classification
    ingestion_status: IngestionStatus
    legal_hold: bool
    matter_id: UUID


class DocumentResponse(DocumentSummary):
    """Full document detail (single-document endpoint)."""

    firm_id: UUID
    file_hash: str
    bates_number: str | None
    uploaded_by: UUID
    created_at: datetime
    updated_at: datetime


class DuplicateCheckResponse(BaseModel):
    """Result of a duplicate-check query against a matter."""

    exists: bool
    document_id: UUID | None = None


class IngestionConfigResponse(BaseModel):
    """Public-facing ingestion configuration — no server internals."""

    allowed_content_types: list[str]
    allowed_extensions: list[str]
