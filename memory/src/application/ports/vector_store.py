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
        """
        pass

    @abstractmethod
    async def delete(self, vector_id: str) -> None:
        """
        Elimina un vector del almacén por su identificador único.
        """
        pass
