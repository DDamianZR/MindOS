"""F1-T1: objeto cognitivo rico (object_type, confidence, importance, status, evidence, salience, tombstone)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-21
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Valores válidos de ObjectType al momento de esta migración (ver mindos_schemas.domain.ObjectType).
# Cualquier valor libre preexistente que no pertenezca a este conjunto se normaliza a 'note'.
_KNOWN_OBJECT_TYPES = (
    "note", "idea", "document", "conversation", "concept", "person", "project", "task",
    "resource", "technology", "event", "observation", "experience", "question", "hypothesis",
    "investigation", "evidence", "decision", "outcome", "learning", "fact", "insight",
)


def upgrade() -> None:
    # `entity_type` (string libre) -> `object_type` (catálogo ObjectType). Renombrar preserva los datos.
    op.alter_column(
        "knowledge_nodes", "entity_type",
        new_column_name="object_type",
        existing_type=sa.String(length=50),
    )
    # Normalizar cualquier valor fuera del catálogo conocido a 'note' (no se pierde el nodo, solo su tipo).
    known = ", ".join(f"'{v}'" for v in _KNOWN_OBJECT_TYPES)
    op.execute(f"UPDATE knowledge_nodes SET object_type = 'note' WHERE object_type NOT IN ({known})")

    # Atributos cognitivos ricos en la versión (F1-T1).
    op.add_column("knowledge_node_versions",
                   sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"))
    op.add_column("knowledge_node_versions",
                   sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"))
    op.add_column("knowledge_node_versions",
                   sa.Column("status", sa.String(length=20), nullable=False, server_default="active"))
    op.add_column("knowledge_node_versions",
                   sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.add_column("knowledge_node_versions",
                   sa.Column("salience", sa.Float(), nullable=False, server_default="0.5"))
    op.add_column("knowledge_node_versions",
                   sa.Column("tombstoned_at", sa.DateTime(timezone=True), nullable=True))

    # Acelera get_latest_node_version(include_archived=False), el camino por defecto de toda lectura.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_versions_active "
        "ON knowledge_node_versions (node_id) WHERE tombstoned_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_versions_active")
    op.drop_column("knowledge_node_versions", "tombstoned_at")
    op.drop_column("knowledge_node_versions", "salience")
    op.drop_column("knowledge_node_versions", "evidence")
    op.drop_column("knowledge_node_versions", "status")
    op.drop_column("knowledge_node_versions", "importance")
    op.drop_column("knowledge_node_versions", "confidence")
    op.alter_column(
        "knowledge_nodes", "object_type",
        new_column_name="entity_type",
        existing_type=sa.String(length=50),
    )
