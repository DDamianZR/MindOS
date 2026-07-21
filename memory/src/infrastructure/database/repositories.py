from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory.src.application.ports.database import DatabasePort
from memory.src.infrastructure.database.models import (
    DbCognitiveObject,
    DbCognitiveRelation,
    DbEventLog,
    DbObjectVersion,
)


class PgDatabaseRepository(DatabasePort):
    """
    Implementación concreta de DatabasePort para PostgreSQL utilizando SQLAlchemy AsyncSession.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_node(self, node_id: UUID, entity_type: str) -> None:
        # Verificar si el nodo ya existe
        stmt = select(DbCognitiveObject).where(DbCognitiveObject.id == node_id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if not existing:
            new_node = DbCognitiveObject(id=node_id, entity_type=entity_type)
            self.session.add(new_node)
            await self.session.flush()

    async def save_node_version(
        self,
        node_id: UUID,
        version: int,
        title: str,
        content: str,
        author: str,
        metadata: dict[str, Any],
        parent_version_id: UUID | None = None
    ) -> None:
        new_version = DbObjectVersion(
            id=UUID(int=hash(f"{node_id}-{version}") & ((1<<128)-1)), # Simular ID versionable
            node_id=node_id,
            version=version,
            title=title,
            content=content,
            author=author,
            metadata_json=metadata,
            parent_version_id=parent_version_id
        )
        self.session.add(new_version)
        await self.session.flush()

    async def get_latest_node_version(self, node_id: UUID) -> dict[str, Any] | None:
        stmt = (
            select(DbObjectVersion)
            .where(DbObjectVersion.node_id == node_id)
            .order_by(DbObjectVersion.version.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        ver = result.scalar_one_or_none()
        if ver:
            return {
                "node_id": ver.node_id,
                "version": ver.version,
                "title": ver.title,
                "content": ver.content,
                "author": ver.author,
                "metadata": ver.metadata_json,
                "created_at": ver.created_at,
                "parent_version_id": ver.parent_version_id
            }
        return None

    async def get_node_versions(self, node_id: UUID) -> list[dict[str, Any]]:
        stmt = (
            select(DbObjectVersion)
            .where(DbObjectVersion.node_id == node_id)
            .order_by(DbObjectVersion.version.asc())
        )
        result = await self.session.execute(stmt)
        versions = result.scalars().all()
        return [
            {
                "node_id": v.node_id,
                "version": v.version,
                "title": v.title,
                "content": v.content,
                "author": v.author,
                "metadata": v.metadata_json,
                "created_at": v.created_at,
                "parent_version_id": v.parent_version_id
            } for v in versions
        ]

    async def save_relation(
        self,
        source_id: UUID,
        target_id: UUID,
        relation_type: str,
        metadata: dict[str, Any]
    ) -> None:
        now = datetime.now(timezone.utc)

        # Desactivar relación previa idéntica si existe
        stmt = (
            update(DbCognitiveRelation)
            .where(
                DbCognitiveRelation.source_id == source_id,
                DbCognitiveRelation.target_id == target_id,
                DbCognitiveRelation.relation_type == relation_type,
                DbCognitiveRelation.valid_to.is_(None)
            )
            .values(valid_to=now)
        )
        await self.session.execute(stmt)

        # Insertar nueva relación activa
        new_rel = DbCognitiveRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            valid_from=now,
            valid_to=None,
            metadata_json=metadata
        )
        self.session.add(new_rel)
        await self.session.flush()

    async def delete_relation(self, source_id: UUID, target_id: UUID, relation_type: str) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(DbCognitiveRelation)
            .where(
                DbCognitiveRelation.source_id == source_id,
                DbCognitiveRelation.target_id == target_id,
                DbCognitiveRelation.relation_type == relation_type,
                DbCognitiveRelation.valid_to.is_(None)
            )
            .values(valid_to=now)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def query_relations_recursive(self, start_node_id: UUID, max_depth: int) -> list[dict[str, Any]]:
        # Consulta recursiva nativa en PostgreSQL para caminar el grafo
        query = text("""
            WITH RECURSIVE graph_nodes AS (
                -- Caso base
                SELECT source_id, target_id, relation_type, valid_from, valid_to, metadata, 1 as depth
                FROM relations
                WHERE source_id = :start_node AND valid_to IS_NULL
                UNION ALL
                -- Caso recursivo
                SELECT r.source_id, r.target_id, r.relation_type, r.valid_from, r.valid_to, r.metadata, gn.depth + 1
                FROM relations r
                INNER JOIN graph_nodes gn ON r.source_id = gn.target_id
                WHERE r.valid_to IS_NULL AND gn.depth < :max_depth
            )
            SELECT source_id, target_id, relation_type, valid_from, valid_to, metadata FROM graph_nodes;
        """)

        # Corrección de sintaxis SQL para IS NULL
        query = text(query.text.replace("IS_NULL", "IS NULL"))

        result = await self.session.execute(
            query,
            {"start_node": start_node_id, "max_depth": max_depth}
        )

        rows = result.fetchall()
        return [
            {
                "source_id": row[0],
                "target_id": row[1],
                "relation_type": row[2],
                "valid_from": row[3],
                "valid_to": row[4],
                "metadata": row[5]
            } for row in rows
        ]

    async def save_event_log(self, event_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
        new_event = DbEventLog(
            event_id=event_id,
            event_type=event_type,
            payload=payload
        )
        self.session.add(new_event)
        await self.session.flush()
