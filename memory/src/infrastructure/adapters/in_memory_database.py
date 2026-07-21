from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from memory.src.application.ports.database import DatabasePort


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
        }
        # Insertar y mantener orden por versión
        self._versions[node_id].append(version_data)
        self._versions[node_id].sort(key=lambda x: x["version"])

    async def get_latest_node_version(
        self, node_id: UUID, include_archived: bool = False
    ) -> dict[str, Any] | None:
        versions = self._versions.get(node_id, [])
        if not include_archived:
            versions = [v for v in versions if v.get("tombstoned_at") is None]
        if versions:
            return versions[-1]  # La última activa
        return None

    async def get_node_versions(self, node_id: UUID) -> list[dict[str, Any]]:
        return self._versions.get(node_id, [])

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

    async def save_event_log(self, event_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
        self._events.append({
            "event_id": event_id,
            "event_type": event_type,
            "payload": payload,
            "logged_at": datetime.now(timezone.utc)
        })
