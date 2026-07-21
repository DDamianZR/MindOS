"""F2-T1: Thinking Graph (reasoning_episodes + reasoning_steps)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-21
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reasoning_episodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("goal", sa.String(), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_output", sa.String(), nullable=True),
    )
    op.create_table(
        "reasoning_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("episode_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("reasoning_episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("input", sa.String(), nullable=True),
        sa.Column("output", sa.String(), nullable=True),
        sa.Column("capability_name", sa.String(length=100), nullable=True),
        sa.Column("approved", sa.Boolean(), nullable=True),
        sa.Column("feedback", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("knowledge_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
    )

    op.create_index("ix_reasoning_steps_episode", "reasoning_steps", ["episode_id"])
    # Acelera get_episodes_by_node / walk_reasoning: buscar episodios/pasos que citan un node_id
    # dentro del arreglo JSONB knowledge_refs.
    op.execute(
        "CREATE INDEX ix_reasoning_steps_knowledge_refs "
        "ON reasoning_steps USING gin (knowledge_refs jsonb_path_ops)"
    )
    op.create_index("ix_reasoning_episodes_correlation", "reasoning_episodes", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_reasoning_episodes_correlation", table_name="reasoning_episodes")
    op.execute("DROP INDEX IF EXISTS ix_reasoning_steps_knowledge_refs")
    op.drop_index("ix_reasoning_steps_episode", table_name="reasoning_steps")
    op.drop_table("reasoning_steps")
    op.drop_table("reasoning_episodes")
