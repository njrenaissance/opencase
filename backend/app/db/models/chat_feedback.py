"""ChatFeedback model — one user rating per chat query turn."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chat_query import ChatQuery


class ChatFeedback(Base):
    __tablename__ = "chat_feedback"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # no index=True — UniqueConstraint below creates the implicit index in PG
    query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_queries.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    flag_bad_citation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chat_query: Mapped[ChatQuery] = relationship(back_populates="feedback")

    __table_args__ = (
        UniqueConstraint("query_id", name="uq_chat_feedback_query_id"),
        CheckConstraint("rating IN (-1, 1)", name="ck_chat_feedback_rating"),
    )
