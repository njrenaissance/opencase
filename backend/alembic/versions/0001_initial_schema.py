"""Initial schema — firms, users, matters, matter_assignments.

Revision ID: 0001
Revises:
Create Date: 2026-03-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TRUE = sa.text("true")
_FALSE = sa.text("false")
_ZERO = sa.text("0")
_NOW = sa.text("now()")


def upgrade() -> None:
    # --- firms ---
    op.create_table(
        "firms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_firms"),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firm_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("title", sa.String(50), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("middle_initial", sa.String(5), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "attorney", "paralegal", "investigator", name="user_role"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=_TRUE),
        sa.Column("totp_secret", sa.String(512), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=_FALSE),
        sa.Column("totp_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default=_ZERO,
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["firm_id"],
            ["firms.id"],
            name="fk_users_firm_id_firms",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("firm_id", "email", name="uq_users_firm_id_email"),
    )
    op.create_index("ix_users_firm_id", "users", ["firm_id"])

    # --- matters ---
    op.create_table(
        "matters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firm_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "closed", "archived", name="matter_status"),
            nullable=False,
        ),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=_FALSE),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["firm_id"],
            ["firms.id"],
            name="fk_matters_firm_id_firms",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_matters"),
    )
    op.create_index("ix_matters_firm_id", "matters", ["firm_id"])
    op.create_index("ix_matters_client_id", "matters", ["client_id"])

    # --- matter_access (security construct — see MatterAccess model docstring) ---
    op.create_table(
        "matter_access",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column(
            "view_work_product",
            sa.Boolean(),
            nullable=False,
            server_default=_FALSE,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["matters.id"],
            name="fk_matter_access_matter_id_matters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_matter_access_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "matter_id", name="pk_matter_access"),
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is not supported. "
        "This project enforces a fix-forward migration policy."
    )
