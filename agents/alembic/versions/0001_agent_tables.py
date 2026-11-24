"""Tablas del servicio de agentes: conversaciones, rutinas, ejecuciones y uso (Fase 9).

Revision ID: 0001_agent_tables
Revises:
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_agent_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("started_at_label", sa.Text(), nullable=False),
        sa.Column("messages", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("transcript", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "agent_routines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("schedule", sa.String(100), nullable=False),
        sa.Column("schedule_description", sa.Text(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_by", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("runs_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_agent_routines_status_next_run", "agent_routines", ["status", "next_run_at"])
    op.create_table(
        "agent_routine_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("routine_id", sa.String(36), sa.ForeignKey("agent_routines.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("output", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.create_index("ix_agent_routine_runs_routine_started", "agent_routine_runs", ["routine_id", "started_at"])
    op.create_index(
        "uq_agent_routine_runs_one_running", "agent_routine_runs", ["routine_id"], unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_table(
        "agent_usage_turns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("tools", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cache_read_input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cache_creation_input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_agent_usage_turns_at", "agent_usage_turns", ["at"])


def downgrade() -> None:
    op.drop_index("ix_agent_usage_turns_at", table_name="agent_usage_turns")
    op.drop_table("agent_usage_turns")
    op.drop_index("uq_agent_routine_runs_one_running", table_name="agent_routine_runs")
    op.drop_index("ix_agent_routine_runs_routine_started", table_name="agent_routine_runs")
    op.drop_table("agent_routine_runs")
    op.drop_index("ix_agent_routines_status_next_run", table_name="agent_routines")
    op.drop_table("agent_routines")
    op.drop_table("agent_conversations")
