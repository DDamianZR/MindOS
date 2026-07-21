from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class DatabasePort(ABC):
    """
    Puerto de infraestructura para operaciones relacionales y del Grafo de Conocimiento.
    Abstrae el almacenamiento y consulta de entidades, versiones históricas y relaciones.
    """
    @abstractmethod
    async def save_node(self, node_id: UUID, entity_type: str) -> None:
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
        parent_version_id: UUID | None = None
    ) -> None:
        """
        Inserta una versión inmutable (snapshot) para el nodo.

        `version_id` es el identificador propio de esta fila de versión (UUIDv7). Debe usarse
        como `parent_version_id` de la siguiente versión para reconstruir el lineaje histórico.
        """
        pass

    @abstractmethod
    async def get_latest_node_version(self, node_id: UUID) -> dict[str, Any] | None:
        """
        Recupera la versión más reciente activa de un nodo.

        El dict devuelto incluye `version_id` (id propio de la fila de versión), necesario para
        encadenar `parent_version_id` correctamente.
        """
        pass

    @abstractmethod
    async def get_node_versions(self, node_id: UUID) -> list[dict[str, Any]]:
        """Recupera cronológicamente todas las versiones históricas de un nodo."""
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
