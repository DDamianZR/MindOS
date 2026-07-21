from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class VectorSearchResult(BaseModel):
    id: str
    score: float
    payload: dict[str, Any]

class VectorStorePort(ABC):
    """
    Puerto de infraestructura para operaciones en la base de datos vectorial.
    Permite independizar el dominio de tecnologías concretas como pgvector, Qdrant o Milvus.

    No expone una operación de borrado: el ciclo de vida de un Objeto Cognitivo (archivar,
    restaurar) se gestiona íntegramente vía `DatabasePort` marcando `tombstoned_at` (F1-T4)
    — nunca borrando el vector físicamente. El almacén vectorial es un índice de similitud
    puro; la noción de "archivado" es un concepto de dominio, no del índice.
    """
    @abstractmethod
    async def upsert(self, vector_id: str, embedding: list[float], payload: dict[str, Any]) -> None:
        """
        Inserta o actualiza un vector en el almacén con sus metadatos asociados.
        """
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        limit: int,
        filters: dict[str, Any] | None = None
    ) -> list[VectorSearchResult]:
        """
        Realiza una búsqueda de similitud coseno sobre el índice vectorial.

        Puede devolver candidatos que luego resulten archivados a nivel de dominio (el
        caller debe filtrarlos vía `DatabasePort.get_latest_node_version(include_archived=False)`);
        por eso conviene pedir más candidatos que el `limit` final deseado.
        """
        pass
