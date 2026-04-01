"""Document router — upload, list, retrieve, and download documents."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response
from opentelemetry import trace
from shared.models.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentSummary,
    DuplicateCheckResponse,
    IngestionConfigResponse,
    ReIngestResponse,
)
from shared.models.enums import Classification, DocumentSource, IngestionStatus, Role
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.metrics import documents_created, documents_duplicates_rejected
from app.core.permissions import fetch_matter_access
from app.db import get_db
from app.db.models.document import Document
from app.db.models.matter_access import MatterAccess
from app.db.models.user import User
from app.storage import get_storage_service
from app.storage.hashing import FileTooLargeError, read_and_hash
from app.storage.s3 import S3StorageService

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SAFE_FILENAME_RE = re.compile(r"[^\w\s\-.,()]+")


def _sanitize_filename(filename: str | None) -> str:
    """Strip path components and dangerous characters from a filename."""
    if not filename:
        return "unnamed"
    # Take only the final path component (strip directory traversal)
    name = PurePosixPath(filename).name
    # Remove characters that aren't word chars, spaces, hyphens, dots, commas, or parens
    name = _SAFE_FILENAME_RE.sub("_", name)
    # Collapse runs of underscores
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "unnamed"


def _extension_from_filename(filename: str | None) -> str:
    """Extract the file extension (without dot) from a filename."""
    if not filename:
        return "bin"
    suffix = PurePosixPath(filename).suffix
    return suffix.lstrip(".").lower() if suffix else "bin"


def _doc_to_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        firm_id=doc.firm_id,
        matter_id=doc.matter_id,
        filename=doc.filename,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        source=doc.source,
        classification=doc.classification,
        ingestion_status=doc.ingestion_status,
        legal_hold=doc.legal_hold,
        file_hash=doc.file_hash,
        bates_number=doc.bates_number,
        uploaded_by=doc.uploaded_by,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _doc_to_summary(doc: Document) -> DocumentSummary:
    return DocumentSummary(
        id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        source=doc.source,
        classification=doc.classification,
        ingestion_status=doc.ingestion_status,
        legal_hold=doc.legal_hold,
        matter_id=doc.matter_id,
    )


async def _verify_matter_access(
    matter_id: uuid.UUID, user: User, db: AsyncSession
) -> None:
    """Check matter access for non-admin users. Raises 404 on failure."""
    if user.role == Role.admin:
        return
    await fetch_matter_access(matter_id, user, db)


async def _get_document_with_access(
    document_id: uuid.UUID, user: User, db: AsyncSession
) -> Document:
    """Fetch a document by ID with firm-scope and matter access check."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.firm_id == user.firm_id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    await _verify_matter_access(doc.matter_id, user, db)
    return doc


# ---------------------------------------------------------------------------
# GET /documents/ingestion-config
# ---------------------------------------------------------------------------


@router.get("/ingestion-config", response_model=IngestionConfigResponse)
async def get_ingestion_config(
    user: User = Depends(get_current_user),  # noqa: B008
) -> IngestionConfigResponse:
    """Return allowed content types and file extensions for ingestion.

    Available to all authenticated users (any role). The CLI needs this
    to filter files during bulk-ingest before uploading.
    """
    return IngestionConfigResponse(
        allowed_content_types=sorted(settings.ingestion.allowed_content_types),
        allowed_extensions=sorted(settings.ingestion.allowed_extensions),
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
    file: UploadFile = File(...),  # noqa: B008
    matter_id: uuid.UUID = Form(...),  # noqa: B008
    source: DocumentSource = Form(DocumentSource.defense),  # noqa: B008
    classification: Classification = Form(Classification.unclassified),  # noqa: B008
    bates_number: str | None = Form(None),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    storage: S3StorageService = Depends(get_storage_service),  # noqa: B008
) -> DocumentResponse:
    """Upload a document to a matter.

    Accepts a multipart form with the file and metadata fields. The server
    computes the SHA-256 hash and checks for duplicates within the matter.
    """
    with tracer.start_as_current_span(
        "documents.create",
        attributes={"user.id": str(user.id), "matter.id": str(matter_id)},
    ):
        # 1. Verify matter access
        await _verify_matter_access(matter_id, user, db)

        # 2. Validate content type
        content_type = file.content_type or "application/octet-stream"
        if content_type not in settings.ingestion.allowed_content_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Content type '{content_type}' is not allowed",
            )

        # 3. Read file + compute SHA-256 (spools to disk for large files)
        try:
            data, file_hash, size_bytes = await read_and_hash(
                file,
                max_bytes=settings.s3.max_upload_bytes,
                spool_threshold=settings.s3.spool_threshold_bytes,
            )
        except FileTooLargeError as exc:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(exc),
            ) from exc

        try:
            # 4. Dedup check via DB unique constraint
            doc_id = uuid.uuid4()
            filename = _sanitize_filename(file.filename)
            extension = _extension_from_filename(file.filename)

            doc = Document(
                id=doc_id,
                firm_id=user.firm_id,
                matter_id=matter_id,
                filename=filename,
                file_hash=file_hash,
                content_type=content_type,
                size_bytes=size_bytes,
                source=source,
                classification=classification,
                ingestion_status=IngestionStatus.pending,
                bates_number=bates_number,
                legal_hold=False,
                uploaded_by=user.id,
            )
            db.add(doc)

            try:
                await db.flush()
            except IntegrityError as exc:
                await db.rollback()
                documents_duplicates_rejected.add(1)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "A document with the same content already exists in this matter"
                    ),
                ) from exc

            # 5. Upload to S3
            try:
                s3_key = await storage.upload_document(
                    firm_id=user.firm_id,
                    matter_id=matter_id,
                    document_id=doc_id,
                    extension=extension,
                    data=data,
                    size=size_bytes,
                    content_type=content_type,
                    file_hash=file_hash,
                )
            except Exception as exc:
                await db.rollback()
                logger.exception("S3 upload failed for document %s", doc_id)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to store file in object storage",
                ) from exc

            # 6. Commit DB transaction (clean up S3 object on failure)
            try:
                await db.commit()
            except Exception as commit_exc:
                logger.exception(
                    "DB commit failed for document %s; removing S3 object",
                    doc_id,
                )
                try:
                    await storage.delete_document(s3_key)
                except Exception:
                    logger.exception(
                        "S3 cleanup also failed for document %s, key %s",
                        doc_id,
                        s3_key,
                    )
                raise commit_exc
            await db.refresh(doc)

            # 7. Fire-and-forget ingestion task
            try:
                from app.ingestion import get_ingestion_service

                ingestion = get_ingestion_service()
                await ingestion.process_document(doc_id, s3_key)
            except Exception:
                # Ingestion failure must not block the upload response.
                # The document is already persisted — ingestion can be
                # retried later.
                logger.exception("Ingestion dispatch failed for document %s", doc_id)

            documents_created.add(1)
            logger.info("Document uploaded: id=%s key=%s", doc_id, s3_key)

            return _doc_to_response(doc)
        finally:
            data.close()


# ---------------------------------------------------------------------------
# GET /documents/check-duplicate
# ---------------------------------------------------------------------------


@router.get("/check-duplicate", response_model=DuplicateCheckResponse)
async def check_duplicate(
    matter_id: uuid.UUID = Query(...),  # noqa: B008
    file_hash: str = Query(  # noqa: B008
        ..., min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$"
    ),
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DuplicateCheckResponse:
    """Check whether a document with the given SHA-256 hash exists in a matter.

    This lightweight endpoint lets clients pre-check before uploading,
    avoiding the bandwidth cost of sending files that would be rejected
    as duplicates.
    """
    # Normalize to lowercase for consistent DB comparison.
    file_hash = file_hash.lower()

    with tracer.start_as_current_span(
        "documents.check_duplicate",
        attributes={"user.id": str(user.id), "matter.id": str(matter_id)},
    ):
        await _verify_matter_access(matter_id, user, db)
        result = await db.execute(
            select(Document.id).where(
                Document.firm_id == user.firm_id,
                Document.matter_id == matter_id,
                Document.file_hash == file_hash,
            )
        )
        existing = result.scalar_one_or_none()
        return DuplicateCheckResponse(
            exists=existing is not None,
            document_id=existing,
        )


# ---------------------------------------------------------------------------
# GET /documents/
# ---------------------------------------------------------------------------


_SORTABLE_COLUMNS = {
    "created_at": Document.created_at,
    "filename": Document.filename,
    "size_bytes": Document.size_bytes,
    "updated_at": Document.updated_at,
}


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    matter_id: uuid.UUID | None = Query(None),  # noqa: B008
    ingestion_status: IngestionStatus | None = Query(None),  # noqa: B008
    source: DocumentSource | None = Query(None),  # noqa: B008
    classification: Classification | None = Query(None),  # noqa: B008
    filename: str | None = Query(None),  # noqa: B008
    offset: int = Query(0, ge=0),  # noqa: B008
    limit: int = Query(50, ge=1, le=200),  # noqa: B008
    sort_by: Literal[  # noqa: B008
        "created_at", "filename", "size_bytes", "updated_at"
    ] = Query("created_at"),
    sort_order: Literal["asc", "desc"] = Query("desc"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DocumentListResponse:
    """List documents accessible to the current user.

    Supports filtering by matter, ingestion status, source, classification,
    and filename (partial, case-insensitive). Results are paginated.
    """
    with tracer.start_as_current_span(
        "documents.list",
        attributes={"user.id": str(user.id)},
    ):
        stmt = select(Document).where(Document.firm_id == user.firm_id)

        if matter_id is not None:
            await _verify_matter_access(matter_id, user, db)
            stmt = stmt.where(Document.matter_id == matter_id)
        elif user.role != Role.admin:
            stmt = stmt.join(
                MatterAccess,
                (MatterAccess.matter_id == Document.matter_id)
                & (MatterAccess.user_id == user.id),
            )

        # Apply filters
        if ingestion_status is not None:
            stmt = stmt.where(Document.ingestion_status == ingestion_status)
        if source is not None:
            stmt = stmt.where(Document.source == source)
        if classification is not None:
            stmt = stmt.where(Document.classification == classification)
        if filename is not None:
            escaped_filename = filename.replace("%", r"\%").replace("_", r"\_")
            stmt = stmt.where(
                Document.filename.ilike(f"%{escaped_filename}%", escape="\\")
            )

        # Count total before pagination (must run before ORDER BY is applied
        # to avoid PostgreSQL requiring ORDER BY expressions in the SELECT list)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        # Sorting
        col = _SORTABLE_COLUMNS[sort_by]
        stmt = stmt.order_by(col.desc() if sort_order == "desc" else col.asc())

        # Pagination
        stmt = stmt.offset(offset).limit(limit)

        result = await db.execute(stmt)
        docs = result.scalars().all()
        return DocumentListResponse(
            items=[_doc_to_summary(d) for d in docs],
            total=total,
            offset=offset,
            limit=limit,
        )


# ---------------------------------------------------------------------------
# GET /documents/{document_id}
# ---------------------------------------------------------------------------


@router.get("/{document_id}", response_model=DocumentResponse, responses={404: {}})
async def get_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DocumentResponse:
    """Retrieve metadata for a single document."""
    with tracer.start_as_current_span(
        "documents.get",
        attributes={"user.id": str(user.id), "document.id": str(document_id)},
    ):
        doc = await _get_document_with_access(document_id, user, db)
        return _doc_to_response(doc)


# ---------------------------------------------------------------------------
# GET /documents/{document_id}/download
# ---------------------------------------------------------------------------


@router.get(
    "/{document_id}/download",
    responses={404: {}, 502: {}},
)
async def download_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    storage: S3StorageService = Depends(get_storage_service),  # noqa: B008
) -> Response:
    """Download the original file for a document."""
    with tracer.start_as_current_span(
        "documents.download",
        attributes={"user.id": str(user.id), "document.id": str(document_id)},
    ):
        doc = await _get_document_with_access(document_id, user, db)

        extension = _extension_from_filename(doc.filename)
        s3_key = S3StorageService.object_key(
            doc.firm_id, doc.matter_id, doc.id, extension
        )

        try:
            file_bytes, _ct = await storage.download_document(s3_key)
        except Exception as exc:
            logger.exception("S3 download failed for document %s", document_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to retrieve file from object storage",
            ) from exc

        encoded_name = quote(doc.filename, safe="")
        ascii_name = doc.filename.encode("ascii", "replace").decode()
        return Response(
            content=file_bytes,
            media_type=doc.content_type,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{ascii_name}"; '
                    f"filename*=UTF-8''{encoded_name}"
                ),
            },
        )


# ---------------------------------------------------------------------------
# POST /documents/{document_id}/re-ingest
# ---------------------------------------------------------------------------


@router.post(
    "/{document_id}/re-ingest",
    response_model=ReIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={404: {}, 409: {}},
)
async def re_ingest_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ReIngestResponse:
    """Re-ingest a document that previously failed ingestion.

    Only documents with ``ingestion_status = failed`` can be re-ingested.
    Resets the status to ``pending`` and dispatches a new ingestion task.
    """
    with tracer.start_as_current_span(
        "documents.re_ingest",
        attributes={"user.id": str(user.id), "document.id": str(document_id)},
    ):
        # Re-ingest is a write operation — restrict to admin and attorney
        if user.role not in (Role.admin, Role.attorney):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins and attorneys can re-ingest documents",
            )

        # Lock the row to prevent concurrent re-ingest races
        result = await db.execute(
            select(Document)
            .where(
                Document.id == document_id,
                Document.firm_id == user.firm_id,
            )
            .with_for_update()
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        await _verify_matter_access(doc.matter_id, user, db)

        if doc.legal_hold:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot re-ingest a document under legal hold",
            )

        if doc.ingestion_status != IngestionStatus.failed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Only failed documents can be re-ingested; "
                    f"current status is '{doc.ingestion_status.value}'"
                ),
            )

        # Reset to pending
        doc.ingestion_status = IngestionStatus.pending
        await db.commit()
        await db.refresh(doc)

        # Reconstruct S3 key and dispatch ingestion
        extension = _extension_from_filename(doc.filename)
        s3_key = S3StorageService.object_key(
            doc.firm_id, doc.matter_id, doc.id, extension
        )

        try:
            from app.ingestion import get_ingestion_service

            ingestion = get_ingestion_service()
            await ingestion.process_document(doc.id, s3_key)
        except Exception:
            logger.exception("Re-ingest dispatch failed for document %s", doc.id)
            doc.ingestion_status = IngestionStatus.failed
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to dispatch ingestion task",
            ) from None

        return ReIngestResponse(
            document_id=doc.id,
            ingestion_status=doc.ingestion_status,
            message="Ingestion task submitted",
        )
