"""Pydantic request/response models for document endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from shared.models.enums import Classification, DocumentSource

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


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class CreateDocumentRequest(BaseModel):
    matter_id: UUID
    filename: str = Field(min_length=1, max_length=512)
    content_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=0)
    file_hash: str = Field(
        min_length=64, max_length=64, description="SHA-256 hex digest"
    )
    source: DocumentSource = DocumentSource.defense
    classification: Classification = Classification.unclassified
    bates_number: str | None = Field(default=None, max_length=100)
