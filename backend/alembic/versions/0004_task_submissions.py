"""Add task_submissions table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOW = sa.text("now()")
_PENDING = sa.text("'PENDING'")


def upgrade() -> None:
    op.create_table(
        "task_submissions",
        sa.Column("id", sa.String(255), nullable=False),
        sa.Column("firm_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_name", sa.String(100), nullable=False, index=True),
        sa.Column("args_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("kwargs_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default=_PENDING),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_NOW,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_task_submissions"),
        sa.ForeignKeyConstraint(
            ["firm_id"],
            ["firms.id"],
            name="fk_task_submissions_firm_id_firms",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_task_submissions_user_id_users",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    raise NotImplementedError("fix-forward policy: downgrades are not supported")
