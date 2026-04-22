"""Add documents and prompts tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-23 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOW = sa.text("now()")
_FALSE = sa.text("false")


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firm_id", sa.Uuid(), nullable=False),
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column(
            "file_hash",
            sa.String(64),
            nullable=False,
            comment="SHA-256 hex digest for deduplication",
        ),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "government_production",
                "defense",
                "court",
                "work_product",
                name="document_source",
            ),
            nullable=False,
        ),
        sa.Column(
            "classification",
            sa.Enum(
                "brady",
                "giglio",
                "jencks",
                "rule16",
                "work_product",
                "inculpatory",
                "unclassified",
                name="classification",
            ),
            nullable=False,
        ),
        sa.Column("bates_number", sa.String(100), nullable=True),
        sa.Column(
            "legal_hold",
            sa.Boolean(),
            nullable=False,
            server_default=_FALSE,
        ),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.ForeignKeyConstraint(
            ["firm_id"],
            ["firms.id"],
            name="fk_documents_firm_id_firms",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["matters.id"],
            name="fk_documents_matter_id_matters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name="fk_documents_uploaded_by_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "matter_id", "file_hash", name="uq_documents_matter_id_file_hash"
        ),
    )
    op.create_index("ix_documents_firm_id", "documents", ["firm_id"])
    op.create_index("ix_documents_matter_id", "documents", ["matter_id"])

    op.create_table(
        "prompts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firm_id", sa.Uuid(), nullable=False),
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_prompts"),
        sa.ForeignKeyConstraint(
            ["firm_id"],
            ["firms.id"],
            name="fk_prompts_firm_id_firms",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["matters.id"],
            name="fk_prompts_matter_id_matters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_prompts_created_by_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_prompts_firm_id", "prompts", ["firm_id"])
    op.create_index("ix_prompts_matter_id", "prompts", ["matter_id"])


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is not supported. "
        "This project enforces a fix-forward migration policy."
    )
