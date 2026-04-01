"""Add ingestion_status column to documents table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-31 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENUM_NAME = "ingestion_status"
_ENUM_VALUES = ("pending", "extracting", "chunking", "embedding", "indexed", "failed")


def upgrade() -> None:
    ingestion_status_enum = sa.Enum(*_ENUM_VALUES, name=_ENUM_NAME)
    ingestion_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "documents",
        sa.Column(
            "ingestion_status",
            ingestion_status_enum,
            nullable=False,
            server_default="pending",
        ),
    )
    op.create_index(
        "ix_documents_ingestion_status",
        "documents",
        ["ingestion_status"],
    )


def downgrade() -> None:
    pass
