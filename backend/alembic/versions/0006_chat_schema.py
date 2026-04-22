"""Replace prompts table with chat_sessions, chat_queries, and chat_feedback.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOW = sa.text("now()")
_FALSE = sa.text("false")


def upgrade() -> None:
    # --- drop the prompts stub (superseded by chat tables) ---
    op.drop_index("ix_prompts_matter_id", table_name="prompts")
    op.drop_index("ix_prompts_firm_id", table_name="prompts")
    op.drop_table("prompts")

    # --- chat_sessions ---
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firm_id", sa.Uuid(), nullable=False),
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_chat_sessions"),
        sa.ForeignKeyConstraint(
            ["firm_id"],
            ["firms.id"],
            name="fk_chat_sessions_firm_id_firms",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["matters.id"],
            name="fk_chat_sessions_matter_id_matters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_chat_sessions_created_by_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_chat_sessions_firm_id", "chat_sessions", ["firm_id"])
    op.create_index("ix_chat_sessions_matter_id", "chat_sessions", ["matter_id"])

    # --- chat_queries ---
    op.create_table(
        "chat_queries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column(
            "retrieval_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_queries"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.id"],
            name="fk_chat_queries_session_id_chat_sessions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_chat_queries_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_chat_queries_session_id", "chat_queries", ["session_id"])
    op.create_index("ix_chat_queries_user_id", "chat_queries", ["user_id"])

    # --- chat_feedback ---
    op.create_table(
        "chat_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("query_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column(
            "flag_bad_citation",
            sa.Boolean(),
            nullable=False,
            server_default=_FALSE,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_feedback"),
        sa.ForeignKeyConstraint(
            ["query_id"],
            ["chat_queries.id"],
            name="fk_chat_feedback_query_id_chat_queries",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("query_id", name="uq_chat_feedback_query_id"),
        sa.CheckConstraint("rating IN (-1, 1)", name="ck_chat_feedback_rating"),
        # uq_chat_feedback_query_id creates the implicit index on query_id
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is not supported. "
        "This project enforces a fix-forward migration policy."
    )
