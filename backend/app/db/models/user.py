"""User model — one row per firm employee/user."""

import enum
import uuid
from datetime import datetime

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


class Role(enum.StrEnum):
    admin = "admin"
    attorney = "attorney"
    paralegal = "paralegal"
    investigator = "investigator"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Identity
    title: Mapped[str | None] = mapped_column(String(50), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_initial: Mapped[str | None] = mapped_column(String(5), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # TOTP — secret stored as AES-256-GCM ciphertext, never plaintext
    totp_secret: Mapped[str | None] = mapped_column(String(512), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    totp_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Login lockout
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    firm: Mapped["Firm"] = relationship(back_populates="users")  # noqa: F821
    matter_access: Mapped[list["MatterAccess"]] = relationship(  # noqa: F821
        back_populates="user", passive_deletes=True
    )

    # Unique email per firm — same email can exist across different firms
    __table_args__ = (
        UniqueConstraint("firm_id", "email", name="uq_users_firm_id_email"),
    )
