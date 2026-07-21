"""F1-T2: provenance (tabla sources + source_id en knowledge_node_versions)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-21
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("uri", sa.String(), nullable=True),
        sa.Column("raw_ref", sa.String(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "knowledge_node_versions",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=True),
    )
    # Acelera la búsqueda de reutilización de fuente por (kind, uri) en la ingesta.
    op.create_index("ix_sources_kind_uri", "sources", ["kind", "uri"])


def downgrade() -> None:
    op.drop_index("ix_sources_kind_uri", table_name="sources")
    op.drop_column("knowledge_node_versions", "source_id")
    op.drop_table("sources")
