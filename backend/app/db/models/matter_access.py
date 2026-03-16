"""MatterAccess — security construct governing matter visibility and work-product
access.

This is not a simple business join table. It is checked by build_qdrant_filter()
on every vector query to enforce per-user, per-matter access control. A user who
is not present in this table for a given matter receives a 404 (not 403) on all
matter-scoped endpoints — no enumeration of matters they cannot see.

Columns:
    view_work_product: When False (default), work-product classified chunks are
        excluded from all Qdrant queries for this user/matter pair, regardless of
        role. Investigators can never receive True. Only Admin can grant it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.matter import Matter
    from app.db.models.user import User


class MatterAccess(Base):
    __tablename__ = "matter_access"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    matter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), primary_key=True
    )
    view_work_product: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="matter_access")
    matter: Mapped[Matter] = relationship(back_populates="access_grants")
