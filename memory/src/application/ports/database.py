from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class DatabasePort(ABC):
    """
    Puerto de infraestructura para operaciones relacionales y del Grafo de Conocimiento.
    Abstrae el almacenamiento y consulta de entidades, versiones históricas y relaciones.
    """
    @abstractmethod
    async def save_node(self, node_id: UUID, object_type: str) -> None:
        """Crea un nodo base inmutable si no existe."""
        pass

    @abstractmethod
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
        """
        Inserta una versión inmutable (snapshot) para el nodo.

        `version_id` es el identificador propio de esta fila de versión (UUIDv7). Debe usarse
        como `parent_version_id` de la siguiente versión para reconstruir el lineaje histórico.

        `confidence`/`importance` (0-1), `status` (draft|active|hypothesis|fact|superseded|archived)
        y `evidence` (lista de `{node_id|url|quote, weight}`) son los atributos cognitivos ricos
        del Objeto Cognitivo (F1-T1). `salience` no se recibe aquí: nace con el default de la
        columna y la recalcula el agente de consolidación (Fase 5).
        """
        pass

    @abstractmethod
    async def get_latest_node_version(
        self, node_id: UUID, include_archived: bool = False
    ) -> dict[str, Any] | None:
        """
        Recupera la versión más reciente activa de un nodo.

        El dict devuelto incluye `version_id` (id propio de la fila de versión, necesario para
        encadenar `parent_version_id`), `object_type` (del nodo padre) y los atributos cognitivos
        ricos (`confidence`, `importance`, `status`, `evidence`, `salience`, `tombstoned_at`).

        Por defecto excluye versiones tombstoneadas (`tombstoned_at IS NOT NULL`); pasar
        `include_archived=True` para incluirlas (F1-T4).
        """
        pass

    @abstractmethod
    async def get_node_versions(self, node_id: UUID) -> list[dict[str, Any]]:
        """Recupera cronológicamente todas las versiones históricas de un nodo (incluye tombstoneadas)."""
        pass

    @abstractmethod
    async def save_relation(
        self,
        source_id: UUID,
        target_id: UUID,
        relation_type: str,
        metadata: dict[str, Any]
    ) -> None:
        """Crea o actualiza una relación temporal activa en el Grafo de Conocimiento."""
        pass

    @abstractmethod
    async def delete_relation(self, source_id: UUID, target_id: UUID, relation_type: str) -> None:
        """Inactiva temporalmente una relación (marca valid_to como la fecha actual)."""
        pass

    @abstractmethod
    async def query_relations_recursive(self, start_node_id: UUID, max_depth: int) -> list[dict[str, Any]]:
        """
        Realiza una consulta recursiva en el grafo de conocimiento para traer
        entidades y relaciones conectadas hasta una profundidad determinada.
        """
        pass

    @abstractmethod
    async def save_event_log(self, event_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
        """Registra un evento de forma inmutable para auditoría y Event Sourcing híbrido."""
        pass
