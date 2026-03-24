"""Document router — stub endpoints for document management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from opentelemetry import trace
from shared.models.document import (
    CreateDocumentRequest,
    DocumentResponse,
    DocumentSummary,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.metrics import documents_created
from app.db import get_db
from app.db.models.user import User

tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stub_document_response(
    doc_id: uuid.UUID,
    body: CreateDocumentRequest,
    user: User,
) -> DocumentResponse:
    now = datetime.now(UTC)
    return DocumentResponse(
        id=doc_id,
        firm_id=user.firm_id,
        matter_id=body.matter_id,
        filename=body.filename,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        source=body.source,
        classification=body.classification,
        legal_hold=False,
        file_hash=body.file_hash,
        bates_number=body.bates_number,
        uploaded_by=user.id,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# POST /documents/
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    body: CreateDocumentRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DocumentResponse:
    """Stub — accepts document metadata and returns a canned response.

    Future: will compute SHA-256, store file in MinIO, and save metadata.
    """
    with tracer.start_as_current_span(
        "documents.create",
        attributes={"user.id": str(user.id), "matter.id": str(body.matter_id)},
    ):
        doc_id = uuid.uuid4()
        documents_created.add(1)
        return _stub_document_response(doc_id, body, user)


# ---------------------------------------------------------------------------
# GET /documents/
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[DocumentSummary])
async def list_documents(
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[DocumentSummary]:
    """Stub — returns an empty list."""
    with tracer.start_as_current_span(
        "documents.list",
        attributes={"user.id": str(user.id)},
    ):
        return []


# ---------------------------------------------------------------------------
# GET /documents/{document_id}
# ---------------------------------------------------------------------------


@router.get("/{document_id}", response_model=DocumentResponse, responses={404: {}})
async def get_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DocumentResponse:
    """Stub — always returns 404."""
    with tracer.start_as_current_span(
        "documents.get",
        attributes={"user.id": str(user.id), "document.id": str(document_id)},
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
