"""Matter model — one row per legal matter within a firm."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from shared.models.enums import MatterStatus
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.firm import Firm
    from app.db.models.matter_access import MatterAccess


class Matter(Base):
    __tablename__ = "matters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    status: Mapped[MatterStatus] = mapped_column(
        Enum(MatterStatus, name="matter_status"),
        nullable=False,
        default=MatterStatus.open,
    )
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    firm: Mapped[Firm] = relationship(back_populates="matters")
    access_grants: Mapped[list[MatterAccess]] = relationship(back_populates="matter")
