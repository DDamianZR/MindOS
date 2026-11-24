from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Date, and_, case, cast, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory.src.application.ports.database import DatabasePort
from memory.src.infrastructure.database.models import (
    DbCognitiveObject,
    DbCognitiveRelation,
    DbEventLog,
    DbObjectVersion,
    DbSource,
)


class PgDatabaseRepository(DatabasePort):
    """
    Implementación concreta de DatabasePort para PostgreSQL utilizando SQLAlchemy AsyncSession.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_node(self, node_id: UUID, object_type: str) -> None:
        # Verificar si el nodo ya existe
        stmt = select(DbCognitiveObject).where(DbCognitiveObject.id == node_id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if not existing:
            new_node = DbCognitiveObject(id=node_id, object_type=object_type)
            self.session.add(new_node)
            await self.session.flush()

    async def save_node_version(
        self,
        node_id: UUID,
        version_id: UUID,
        version: int,
        title: str,
        content: str,
        author: str,
        metadata: dict[str, Any],
        parent_version_id: UUID | None = None,
        confidence: float = 0.5,
        importance: float = 0.5,
        status: str = "active",
        evidence: list[dict[str, Any]] | None = None,
        provenance_source_id: UUID | None = None,
    ) -> None:
        new_version = DbObjectVersion(
            id=version_id,
            node_id=node_id,
            version=version,
            title=title,
            content=content,
            author=author,
            metadata_json=metadata,
            parent_version_id=parent_version_id,
            confidence=confidence,
            importance=importance,
            status=status,
            evidence=evidence or [],
            source_id=provenance_source_id,
        )
        self.session.add(new_version)
        await self.session.flush()

    def _version_row_to_dict(self, ver: DbObjectVersion, object_type: str | None) -> dict[str, Any]:
        return {
            "node_id": ver.node_id,
            "version_id": ver.id,
            "version": ver.version,
            "title": ver.title,
            "content": ver.content,
            "author": ver.author,
            "metadata": ver.metadata_json,
            "created_at": ver.created_at,
            "parent_version_id": ver.parent_version_id,
            "object_type": object_type,
            "confidence": ver.confidence,
            "importance": ver.importance,
            "status": ver.status,
            "evidence": ver.evidence,
            "salience": ver.salience,
            "tombstoned_at": ver.tombstoned_at,
            "provenance_source_id": ver.source_id,
        }

    async def get_latest_node_version(
        self, node_id: UUID, include_archived: bool = False
    ) -> dict[str, Any] | None:
        # Siempre se busca la versión de mayor número (SIN filtrar por tombstone en la query):
        # si la más reciente está archivada, el nodo se considera archivado y no se retrocede
        # a una versión antigua activa.
        stmt = (
            select(DbObjectVersion, DbCognitiveObject.object_type)
            .join(DbCognitiveObject, DbObjectVersion.node_id == DbCognitiveObject.id)
            .where(DbObjectVersion.node_id == node_id)
            .order_by(DbObjectVersion.version.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if not row:
            return None

        ver, object_type = row
        if not include_archived and ver.tombstoned_at is not None:
            return None
        return self._version_row_to_dict(ver, object_type)

    async def get_node_versions(self, node_id: UUID) -> list[dict[str, Any]]:
        stmt = (
            select(DbObjectVersion, DbCognitiveObject.object_type)
            .join(DbCognitiveObject, DbObjectVersion.node_id == DbCognitiveObject.id)
            .where(DbObjectVersion.node_id == node_id)
            .order_by(DbObjectVersion.version.asc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [self._version_row_to_dict(v, object_type) for v, object_type in rows]

    async def get_node_version_asof(self, node_id: UUID, at: datetime) -> dict[str, Any] | None:
        stmt = (
            select(DbObjectVersion, DbCognitiveObject.object_type)
            .join(DbCognitiveObject, DbObjectVersion.node_id == DbCognitiveObject.id)
            .where(DbObjectVersion.node_id == node_id, DbObjectVersion.created_at <= at)
            .order_by(DbObjectVersion.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row:
            ver, object_type = row
            return self._version_row_to_dict(ver, object_type)
        return None

    async def list_node_versions_since(self, since: datetime | None, limit: int) -> list[dict[str, Any]]:
        # DISTINCT ON (node_id) + ORDER BY version DESC: la última versión ACTIVA de cada nodo.
        query = text("""
            SELECT * FROM (
                SELECT DISTINCT ON (v.node_id)
                    v.id, v.node_id, v.version, v.title, v.content, v.metadata, v.created_at,
                    v.author, v.parent_version_id, v.confidence, v.importance, v.status,
                    v.evidence, v.salience, v.tombstoned_at, v.source_id, n.object_type
                FROM knowledge_node_versions v
                JOIN knowledge_nodes n ON v.node_id = n.id
                WHERE v.tombstoned_at IS NULL
                ORDER BY v.node_id, v.version DESC
            ) latest
            WHERE (:since IS NULL OR created_at >= :since)
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        result = await self.session.execute(query, {"since": since, "limit": limit})
        rows = result.mappings().all()
        return [
            {
                "node_id": r["node_id"], "version_id": r["id"], "version": r["version"],
                "title": r["title"], "content": r["content"], "author": r["author"],
                "metadata": r["metadata"], "created_at": r["created_at"],
                "parent_version_id": r["parent_version_id"], "object_type": r["object_type"],
                "confidence": r["confidence"], "importance": r["importance"], "status": r["status"],
                "evidence": r["evidence"], "salience": r["salience"], "tombstoned_at": r["tombstoned_at"],
                "provenance_source_id": r["source_id"],
            } for r in rows
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

    async def query_incoming_relations(self, target_node_id: UUID, max_depth: int) -> list[dict[str, Any]]:
        # Variante inversa (F2-T3): camina el grafo HACIA ATRÁS por target_id, base de /explain.
        query = text("""
            WITH RECURSIVE graph_nodes AS (
                SELECT source_id, target_id, relation_type, valid_from, valid_to, metadata, 1 as depth
                FROM relations
                WHERE target_id = :target_node AND valid_to IS_NULL
                UNION ALL
                SELECT r.source_id, r.target_id, r.relation_type, r.valid_from, r.valid_to, r.metadata, gn.depth + 1
                FROM relations r
                INNER JOIN graph_nodes gn ON r.target_id = gn.source_id
                WHERE r.valid_to IS_NULL AND gn.depth < :max_depth
            )
            SELECT source_id, target_id, relation_type, valid_from, valid_to, metadata FROM graph_nodes;
        """)
        query = text(query.text.replace("IS_NULL", "IS NULL"))

        result = await self.session.execute(
            query,
            {"target_node": target_node_id, "max_depth": max_depth}
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

    async def query_relations_asof(
        self, start_node_id: UUID, at: datetime, max_depth: int
    ) -> list[dict[str, Any]]:
        # Variante bitemporal (F1-T3): solo sigue relaciones vigentes en el instante `:at`.
        query = text("""
            WITH RECURSIVE graph_nodes AS (
                SELECT source_id, target_id, relation_type, valid_from, valid_to, metadata, 1 as depth
                FROM relations
                WHERE source_id = :start_node
                  AND valid_from <= :at AND (valid_to IS NULL OR valid_to > :at)
                UNION ALL
                SELECT r.source_id, r.target_id, r.relation_type, r.valid_from, r.valid_to, r.metadata, gn.depth + 1
                FROM relations r
                INNER JOIN graph_nodes gn ON r.source_id = gn.target_id
                WHERE r.valid_from <= :at AND (r.valid_to IS NULL OR r.valid_to > :at)
                  AND gn.depth < :max_depth
            )
            SELECT source_id, target_id, relation_type, valid_from, valid_to, metadata FROM graph_nodes;
        """)

        result = await self.session.execute(
            query,
            {"start_node": start_node_id, "at": at, "max_depth": max_depth}
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

    def _source_row_to_dict(self, src: DbSource) -> dict[str, Any]:
        return {
            "id": src.id,
            "kind": src.kind,
            "uri": src.uri,
            "raw_ref": src.raw_ref,
            "captured_at": src.captured_at,
            "metadata": src.metadata_json,
        }

    async def find_source_by_kind_uri(self, kind: str, uri: str) -> dict[str, Any] | None:
        stmt = select(DbSource).where(DbSource.kind == kind, DbSource.uri == uri).limit(1)
        result = await self.session.execute(stmt)
        src = result.scalar_one_or_none()
        return self._source_row_to_dict(src) if src else None

    async def save_source(
        self, source_id: UUID, kind: str, uri: str | None, raw_ref: str | None, metadata: dict[str, Any]
    ) -> None:
        new_source = DbSource(id=source_id, kind=kind, uri=uri, raw_ref=raw_ref, metadata_json=metadata)
        self.session.add(new_source)
        await self.session.flush()

    async def get_source(self, source_id: UUID) -> dict[str, Any] | None:
        stmt = select(DbSource).where(DbSource.id == source_id)
        result = await self.session.execute(stmt)
        src = result.scalar_one_or_none()
        return self._source_row_to_dict(src) if src else None

    async def set_latest_version_tombstone(self, node_id: UUID, tombstoned: bool) -> bool:
        stmt = (
            select(DbObjectVersion)
            .where(DbObjectVersion.node_id == node_id)
            .order_by(DbObjectVersion.version.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        ver = result.scalar_one_or_none()
        if ver is None:
            return False

        ver.tombstoned_at = datetime.now(timezone.utc) if tombstoned else None
        await self.session.flush()
        return True

    async def get_stats_snapshot(self) -> dict[str, Any]:
        statements = _stats_statements()
        nodes = await self._scalar_int(statements["nodes"])
        archived_nodes = await self._scalar_int(statements["archived_nodes"])
        versions = await self._scalar_int(statements["versions"])
        relations = await self._scalar_int(statements["relations"])
        sources = await self._scalar_int(statements["sources"])
        contradictions = await self._scalar_int(statements["contradictions"])

        by_type_rows = await self.session.execute(statements["by_type"])
        by_source_rows = await self.session.execute(statements["by_source"])
        by_relation_rows = await self.session.execute(statements["by_relation"])
        activity_rows = await self.session.execute(statements["activity"])
        recent_rows = await self.session.execute(statements["recent_thinking"])

        return {
            "nodes": nodes,
            "archived_nodes": archived_nodes,
            "versions": versions,
            "relations": relations,
            "sources": sources,
            "contradictions": contradictions,
            "by_type": [{"key": key, "count": int(count)} for key, count in by_type_rows.all() if key is not None],
            "by_source": [{"key": key, "count": int(count)} for key, count in by_source_rows.all()],
            "by_relation": [{"key": key, "count": int(count)} for key, count in by_relation_rows.all()],
            "activity": [
                {"date": day, "created": int(created or 0), "updated": int(updated or 0)}
                for day, created, updated in activity_rows.all()
            ],
            "recent_thinking": [
                {
                    "node_id": node_id,
                    "title": title,
                    "object_type": object_type,
                    "version": int(version),
                    "created_at": created_at,
                }
                for node_id, title, object_type, version, created_at in recent_rows.all()
            ],
        }

    async def _scalar_int(self, stmt) -> int:
        value = await self.session.scalar(stmt)
        return int(value or 0)


# Tipos de pensamiento que pide la portada. El servicio vuelve a filtrar y recorta a 8.
_THINKING_TYPES = ("decision", "insight", "learning", "hypothesis")


def _latest_version_subquery():
    """
    Versión de mayor número de cada nodo. Archivar marca solo esa fila: una versión
    anterior sin tombstone no debe volver a contar el nodo como vigente.
    """
    max_version = (
        select(
            DbObjectVersion.node_id.label("node_id"),
            func.max(DbObjectVersion.version).label("max_version"),
        )
        .group_by(DbObjectVersion.node_id)
        .subquery()
    )
    return (
        select(
            DbObjectVersion.node_id.label("node_id"),
            DbObjectVersion.version.label("version"),
            DbObjectVersion.title.label("title"),
            DbObjectVersion.created_at.label("created_at"),
            DbObjectVersion.tombstoned_at.label("tombstoned_at"),
            DbCognitiveObject.object_type.label("object_type"),
        )
        .join(
            max_version,
            and_(
                DbObjectVersion.node_id == max_version.c.node_id,
                DbObjectVersion.version == max_version.c.max_version,
            ),
        )
        .join(DbCognitiveObject, DbCognitiveObject.id == DbObjectVersion.node_id)
        .subquery()
    )


def _stats_statements() -> dict[str, Any]:
    """Consultas agregadas (count / group by). Ninguna trae las filas sueltas a Python."""
    latest = _latest_version_subquery()
    active_relation = DbCognitiveRelation.valid_to.is_(None)
    day_expr = cast(func.timezone("UTC", DbObjectVersion.created_at), Date)
    return {
        "nodes": select(func.count()).select_from(latest).where(latest.c.tombstoned_at.is_(None)),
        "archived_nodes": select(func.count()).select_from(latest).where(latest.c.tombstoned_at.is_not(None)),
        "versions": select(func.count()).select_from(DbObjectVersion),
        "relations": select(func.count()).select_from(DbCognitiveRelation).where(active_relation),
        "sources": select(func.count()).select_from(DbSource),
        "contradictions": select(func.count()).select_from(DbCognitiveRelation).where(
            active_relation,
            DbCognitiveRelation.relation_type == "CONTRADICTS",
        ),
        "by_type": (
            select(latest.c.object_type, func.count())
            .where(latest.c.tombstoned_at.is_(None))
            .group_by(latest.c.object_type)
        ),
        "by_source": select(DbSource.kind, func.count()).group_by(DbSource.kind),
        "by_relation": (
            select(DbCognitiveRelation.relation_type, func.count())
            .where(active_relation)
            .group_by(DbCognitiveRelation.relation_type)
        ),
        "activity": select(
            day_expr.label("day"),
            func.sum(case((DbObjectVersion.version == 1, 1), else_=0)).label("created"),
            func.sum(case((DbObjectVersion.version > 1, 1), else_=0)).label("updated"),
        ).group_by(day_expr),
        "recent_thinking": (
            select(
                latest.c.node_id,
                latest.c.title,
                latest.c.object_type,
                latest.c.version,
                latest.c.created_at,
            )
            .where(
                latest.c.tombstoned_at.is_(None),
                latest.c.object_type.in_(_THINKING_TYPES),
            )
            .order_by(latest.c.created_at.desc())
            .limit(8)
        ),
    }
