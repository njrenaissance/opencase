"""Firm model — one row per law firm (single-tenant deployment)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.matter import Matter
    from app.db.models.user import User


class Firm(Base):
    __tablename__ = "firms"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # passive_deletes=True: DB-level CASCADE handles child deletion; ORM does not
    # attempt to nullify FKs before the DELETE is issued.
    users: Mapped[list[User]] = relationship(
        back_populates="firm", passive_deletes=True
    )
    matters: Mapped[list[Matter]] = relationship(
        back_populates="firm", passive_deletes=True
    )
