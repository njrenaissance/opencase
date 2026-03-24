"""Document model — one row per uploaded document within a matter."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from shared.models.enums import Classification, DocumentSource
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.firm import Firm
    from app.db.models.matter import Matter
    from app.db.models.user import User


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    matter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 hex digest for deduplication"
    )
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[DocumentSource] = mapped_column(
        Enum(DocumentSource, name="document_source"),
        nullable=False,
        default=DocumentSource.defense,
    )
    classification: Mapped[Classification] = mapped_column(
        Enum(Classification, name="classification"),
        nullable=False,
        default=Classification.unclassified,
    )
    bates_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    firm: Mapped[Firm] = relationship()
    matter: Mapped[Matter] = relationship()
    uploader: Mapped[User] = relationship()

    # Same file (by hash) within the same matter is a duplicate
    __table_args__ = (
        UniqueConstraint(
            "matter_id", "file_hash", name="uq_documents_matter_id_file_hash"
        ),
    )
