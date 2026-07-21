"""initial schema (knowledge nodes, versions, relations, event log)

Revision ID: 0001
Revises:
Create Date: 2026-07-21
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from memory.src.config import settings

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # La extensión pgvector debe existir antes de crear columnas Vector.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "knowledge_node_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("embedding", Vector(settings.EMBEDDING_DIM), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("author", sa.String(length=100), nullable=False),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_node_versions.id"), nullable=True),
        sa.UniqueConstraint("node_id", "version", name="uidx_node_version"),
    )

    op.create_table(
        "relations",
        sa.Column("source_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("relation_type", sa.String(length=50), primary_key=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.func.now(), primary_key=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    op.create_table(
        "knowledge_event_log",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("logged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Índice ANN (HNSW, distancia coseno) para la búsqueda vectorial.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_versions_embedding "
        "ON knowledge_node_versions USING hnsw (embedding vector_cosine_ops)"
    )
    # Índice para caminatas de grafo sobre relaciones activas.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_relations_source_active "
        "ON relations (source_id) WHERE valid_to IS NULL"
    )
    # Índice temporal (timeline / consultas as-of por fecha de versión).
    op.create_index("ix_versions_created_at", "knowledge_node_versions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_versions_created_at", table_name="knowledge_node_versions")
    op.execute("DROP INDEX IF EXISTS ix_relations_source_active")
    op.execute("DROP INDEX IF EXISTS ix_versions_embedding")
    op.drop_table("knowledge_event_log")
    op.drop_table("relations")
    op.drop_table("knowledge_node_versions")
    op.drop_table("knowledge_nodes")
