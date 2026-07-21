from abc import ABC, abstractmethod
from datetime import datetime
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
        provenance_source_id: UUID | None = None,
    ) -> None:
        """
        Inserta una versión inmutable (snapshot) para el nodo.

        `version_id` es el identificador propio de esta fila de versión (UUIDv7). Debe usarse
        como `parent_version_id` de la siguiente versión para reconstruir el lineaje histórico.

        `confidence`/`importance` (0-1), `status` (draft|active|hypothesis|fact|superseded|archived)
        y `evidence` (lista de `{node_id|url|quote, weight}`) son los atributos cognitivos ricos
        del Objeto Cognitivo (F1-T1). `salience` no se recibe aquí: nace con el default de la
        columna y la recalcula el agente de consolidación (Fase 5).

        `provenance_source_id` (F1-T2) enlaza esta versión con su `Source` de origen (whatsapp,
        pdf, cli, ...). Se nombra distinto de `source_id`/`target_id` de las relaciones del grafo
        para evitar ambigüedad: aquí "source" significa procedencia, no nodo origen de una arista.
        """
        pass

    @abstractmethod
    async def get_latest_node_version(
        self, node_id: UUID, include_archived: bool = False
    ) -> dict[str, Any] | None:
        """
        Recupera la versión más reciente (mayor número de versión) de un nodo.

        El dict devuelto incluye `version_id` (id propio de la fila de versión, necesario para
        encadenar `parent_version_id`), `object_type` (del nodo padre), los atributos cognitivos
        ricos (`confidence`, `importance`, `status`, `evidence`, `salience`, `tombstoned_at`) y
        `provenance_source_id` (F1-T2, la fuente de origen si la hay).

        Por defecto (`include_archived=False`), si la versión más reciente está tombstoneada
        (F1-T4, "el nodo está archivado"), devuelve `None` en vez de retroceder a una versión
        antigua activa — eso resucitaría contenido desactualizado sin avisar. Pasar
        `include_archived=True` para recuperarla igualmente.
        """
        pass

    @abstractmethod
    async def get_node_versions(self, node_id: UUID) -> list[dict[str, Any]]:
        """Recupera cronológicamente todas las versiones históricas de un nodo (incluye tombstoneadas)."""
        pass

    @abstractmethod
    async def set_latest_version_tombstone(self, node_id: UUID, tombstoned: bool) -> bool:
        """
        Marca (archivar, `tombstoned=True`) o desmarca (restaurar, `tombstoned=False`) como
        tombstoneada la versión más reciente del nodo (F1-T4, soft-delete). Nunca borra la fila:
        solo actualiza `tombstoned_at`. Devuelve `False` si el nodo no existe.
        """
        pass

    @abstractmethod
    async def get_node_version_asof(self, node_id: UUID, at: datetime) -> dict[str, Any] | None:
        """
        Consulta temporal "as-of" (F1-T3): la versión vigente del nodo en el instante `at`
        (la de mayor `created_at <= at`). Permite reconstruir "qué pensaba en esa fecha".
        Incluye versiones tombstoneadas: el viaje en el tiempo muestra el estado real de
        entonces, independientemente de que hoy esté archivado.
        """
        pass

    # --- Provenance (F1-T2) ---

    @abstractmethod
    async def find_source_by_kind_uri(self, kind: str, uri: str) -> dict[str, Any] | None:
        """Busca una fuente existente por (kind, uri) para reutilizarla en vez de duplicarla."""
        pass

    @abstractmethod
    async def save_source(
        self, source_id: UUID, kind: str, uri: str | None, raw_ref: str | None, metadata: dict[str, Any]
    ) -> None:
        """Crea una nueva fuente de origen (provenance): whatsapp, pdf, imagen, audio, web, cli, api, agente."""
        pass

    @abstractmethod
    async def get_source(self, source_id: UUID) -> dict[str, Any] | None:
        """Recupera una fuente de origen por su id."""
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
    async def query_relations_asof(
        self, start_node_id: UUID, at: datetime, max_depth: int
    ) -> list[dict[str, Any]]:
        """
        Variante bitemporal de `query_relations_recursive` (F1-T3): solo sigue relaciones
        vigentes en el instante `at` (`valid_from <= at AND (valid_to IS NULL OR valid_to > at)`).
        """
        pass

    @abstractmethod
    async def save_event_log(self, event_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
        """Registra un evento de forma inmutable para auditoría y Event Sourcing híbrido."""
        pass
