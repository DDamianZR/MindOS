from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from memory.src.application.ports.database import DatabasePort

# Mismos tipos que recorta StatsService. Filtrar aquí evita recorrer notas en el recuento reciente.
_THINKING_TYPES = frozenset({"decision", "insight", "learning", "hypothesis"})


class InMemoryDatabase(DatabasePort):
    """
    Implementación en memoria de DatabasePort para simulación y pruebas del Kernel.
    Mantiene diccionarios para nodos, versiones, relaciones y logs de eventos,
    e implementa búsqueda recursiva del Grafo de Conocimiento y Pensamiento.
    """
    def __init__(self):
        self._nodes: dict[UUID, dict[str, Any]] = {}
        self._versions: dict[UUID, list[dict[str, Any]]] = {}
        self._relations: list[dict[str, Any]] = []
        self._events: list[dict[str, Any]] = []
        self._sources: dict[UUID, dict[str, Any]] = {}

    async def save_node(self, node_id: UUID, object_type: str) -> None:
        if node_id not in self._nodes:
            self._nodes[node_id] = {
                "id": node_id,
                "object_type": object_type,
                "created_at": datetime.now(timezone.utc)
            }

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
        if node_id not in self._versions:
            self._versions[node_id] = []

        version_data = {
            "node_id": node_id,
            "version_id": version_id,
            "version": version,
            "title": title,
            "content": content,
            "author": author,
            "metadata": metadata,
            "created_at": datetime.now(timezone.utc),
            "parent_version_id": parent_version_id,
            "object_type": self._nodes.get(node_id, {}).get("object_type"),
            "confidence": confidence,
            "importance": importance,
            "status": status,
            "evidence": evidence or [],
            "salience": 0.5,
            "tombstoned_at": None,
            "provenance_source_id": provenance_source_id,
        }
        # Insertar y mantener orden por versión
        self._versions[node_id].append(version_data)
        self._versions[node_id].sort(key=lambda x: x["version"])

    async def get_latest_node_version(
        self, node_id: UUID, include_archived: bool = False
    ) -> dict[str, Any] | None:
        versions = self._versions.get(node_id, [])
        if not versions:
            return None
        latest = versions[-1]  # La versión de mayor número, tombstoneada o no.
        # Si la más reciente está archivada, el nodo se considera archivado: NO se retrocede
        # a una versión antigua activa (eso resucitaría contenido desactualizado sin avisar).
        if not include_archived and latest.get("tombstoned_at") is not None:
            return None
        return latest

    async def get_node_versions(self, node_id: UUID) -> list[dict[str, Any]]:
        return self._versions.get(node_id, [])

    async def get_node_version_asof(self, node_id: UUID, at: datetime) -> dict[str, Any] | None:
        candidates = [v for v in self._versions.get(node_id, []) if v["created_at"] <= at]
        if not candidates:
            return None
        return max(candidates, key=lambda v: v["created_at"])

    async def list_node_versions_since(self, since: datetime | None, limit: int) -> list[dict[str, Any]]:
        latest_versions = []
        for versions in self._versions.values():
            if not versions:
                continue
            latest = versions[-1]
            if latest.get("tombstoned_at") is not None:
                continue
            if since is not None and latest["created_at"] < since:
                continue
            latest_versions.append(latest)
        latest_versions.sort(key=lambda v: v["created_at"], reverse=True)
        return latest_versions[:limit]

    async def save_relation(
        self,
        source_id: UUID,
        target_id: UUID,
        relation_type: str,
        metadata: dict[str, Any]
    ) -> None:
        # Buscar si ya existe la relación activa y desactivarla o actualizarla
        now = datetime.now(timezone.utc)
        for rel in self._relations:
            if (rel["source_id"] == source_id and
                rel["target_id"] == target_id and
                rel["relation_type"] == relation_type and
                rel["valid_to"] is None):
                rel["valid_to"] = now

        # Insertar la nueva relación activa
        self._relations.append({
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
            "valid_from": now,
            "valid_to": None,
            "metadata": metadata
        })

    async def delete_relation(self, source_id: UUID, target_id: UUID, relation_type: str) -> None:
        now = datetime.now(timezone.utc)
        for rel in self._relations:
            if (rel["source_id"] == source_id and
                rel["target_id"] == target_id and
                rel["relation_type"] == relation_type and
                rel["valid_to"] is None):
                rel["valid_to"] = now

    async def query_relations_recursive(self, start_node_id: UUID, max_depth: int) -> list[dict[str, Any]]:
        visited = set()
        results = []

        def traverse(node_id: UUID, current_depth: int):
            if current_depth > max_depth or node_id in visited:
                return

            visited.add(node_id)

            # Buscar relaciones salientes activas
            for rel in self._relations:
                if rel["source_id"] == node_id and rel["valid_to"] is None:
                    results.append(rel)
                    traverse(rel["target_id"], current_depth + 1)

        traverse(start_node_id, 1)
        return results

    async def query_incoming_relations(self, target_node_id: UUID, max_depth: int) -> list[dict[str, Any]]:
        visited = set()
        results = []

        def traverse(node_id: UUID, current_depth: int):
            if current_depth > max_depth or node_id in visited:
                return

            visited.add(node_id)

            # Buscar relaciones ENTRANTES activas (camina hacia atrás por target_id)
            for rel in self._relations:
                if rel["target_id"] == node_id and rel["valid_to"] is None:
                    results.append(rel)
                    traverse(rel["source_id"], current_depth + 1)

        traverse(target_node_id, 1)
        return results

    async def query_relations_asof(
        self, start_node_id: UUID, at: datetime, max_depth: int
    ) -> list[dict[str, Any]]:
        visited = set()
        results = []

        def is_active_at(rel: dict[str, Any]) -> bool:
            return rel["valid_from"] <= at and (rel["valid_to"] is None or rel["valid_to"] > at)

        def traverse(node_id: UUID, current_depth: int):
            if current_depth > max_depth or node_id in visited:
                return

            visited.add(node_id)

            for rel in self._relations:
                if rel["source_id"] == node_id and is_active_at(rel):
                    results.append(rel)
                    traverse(rel["target_id"], current_depth + 1)

        traverse(start_node_id, 1)
        return results

    async def save_event_log(self, event_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
        self._events.append({
            "event_id": event_id,
            "event_type": event_type,
            "payload": payload,
            "logged_at": datetime.now(timezone.utc)
        })

    async def set_latest_version_tombstone(self, node_id: UUID, tombstoned: bool) -> bool:
        versions = self._versions.get(node_id, [])
        if not versions:
            return False
        versions[-1]["tombstoned_at"] = datetime.now(timezone.utc) if tombstoned else None
        return True

    async def find_source_by_kind_uri(self, kind: str, uri: str) -> dict[str, Any] | None:
        for src in self._sources.values():
            if src["kind"] == kind and src["uri"] == uri:
                return src
        return None

    async def save_source(
        self, source_id: UUID, kind: str, uri: str | None, raw_ref: str | None, metadata: dict[str, Any]
    ) -> None:
        self._sources[source_id] = {
            "id": source_id,
            "kind": kind,
            "uri": uri,
            "raw_ref": raw_ref,
            "captured_at": datetime.now(timezone.utc),
            "metadata": metadata,
        }

    async def get_source(self, source_id: UUID) -> dict[str, Any] | None:
        return self._sources.get(source_id)

    async def get_stats_snapshot(self) -> dict[str, Any]:
        activity: dict[date, dict[str, int]] = {}
        latest: list[dict[str, Any]] = []
        versions = 0
        for node_versions in self._versions.values():
            if not node_versions:
                continue
            versions += len(node_versions)
            # La de mayor número es la vigente: si esa está tombstoneada, el nodo está archivado.
            latest.append(node_versions[-1])
            for ver in node_versions:
                _accumulate_activity(activity, ver["version"], ver["created_at"])

        active = [ver for ver in latest if ver.get("tombstoned_at") is None]
        active_relations = [rel for rel in self._relations if rel["valid_to"] is None]
        return {
            "nodes": len(active),
            "archived_nodes": len(latest) - len(active),
            "versions": versions,
            "relations": len(active_relations),
            "sources": len(self._sources),
            "contradictions": sum(1 for rel in active_relations if rel["relation_type"] == "CONTRADICTS"),
            "by_type": _tally(ver["object_type"] for ver in active if ver.get("object_type")),
            "by_source": _tally(src["kind"] for src in self._sources.values()),
            "by_relation": _tally(rel["relation_type"] for rel in active_relations),
            "activity": [
                {"date": day, "created": counts["created"], "updated": counts["updated"]}
                for day, counts in activity.items()
            ],
            "recent_thinking": [
                {
                    "node_id": ver["node_id"],
                    "title": ver["title"],
                    "object_type": ver.get("object_type"),
                    "version": ver["version"],
                    "created_at": ver["created_at"],
                }
                for ver in active
                if ver.get("object_type") in _THINKING_TYPES
            ],
        }


def _utc_day(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date()


def _accumulate_activity(activity: dict[date, dict[str, int]], version: int, created_at: datetime) -> None:
    bucket = activity.setdefault(_utc_day(created_at), {"created": 0, "updated": 0})
    if version == 1:
        bucket["created"] += 1
    elif version > 1:
        bucket["updated"] += 1


def _tally(values) -> list[dict[str, Any]]:
    totals: dict[str, int] = {}
    for value in values:
        totals[value] = totals.get(value, 0) + 1
    return [{"key": key, "count": count} for key, count in totals.items()]
