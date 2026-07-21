from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memory.src.application.ports.vector_store import VectorSearchResult, VectorStorePort
from memory.src.infrastructure.database.models import DbObjectVersion


class PgVectorStoreRepository(VectorStorePort):
    """
    Implementación concreta de VectorStorePort utilizando pgvector integrado en PostgreSQL
    a través de las columnas de la tabla DbObjectVersion en SQLAlchemy.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, vector_id: str, embedding: list[float], payload: dict[str, Any]) -> None:
        node_id = UUID(vector_id)

        # Buscar la última versión del nodo registrado para asociar el vector
        stmt = (
            select(DbObjectVersion)
            .where(DbObjectVersion.node_id == node_id)
            .order_by(DbObjectVersion.version.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        latest_version = result.scalar_one_or_none()

        if latest_version:
            latest_version.embedding = embedding
            await self.session.flush()

    async def search(
        self,
        query_embedding: list[float],
        limit: int,
        filters: dict[str, Any] | None = None
    ) -> list[VectorSearchResult]:
        # Búsqueda semántica usando el operador de distancia coseno de pgvector (<=>)
        # Ordena ascendentemente por distancia, lo que equivale a mayor similitud coseno
        stmt = (
            select(DbObjectVersion)
            .where(DbObjectVersion.embedding.isnot(None))
            .order_by(DbObjectVersion.embedding.cosine_distance(query_embedding).asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        versions = result.scalars().all()

        # Mapear las filas de versiones de SQLAlchemy al DTO genérico del puerto VectorSearchResult
        return [
            VectorSearchResult(
                id=str(v.node_id),
                score=1.0, # El ordenamiento es garantizado por la consulta de la DB (SQL operator <=> )
                payload={
                    "title": v.title,
                    "type": "note",
                    "metadata": v.metadata_json
                }
            ) for v in versions
        ]

    async def delete(self, vector_id: str) -> None:
        node_id = UUID(vector_id)
        # Limpiar el campo de embedding
        stmt = (
            update(DbObjectVersion)
            .where(DbObjectVersion.node_id == node_id)
            .values(embedding=None)
        )
        await self.session.execute(stmt)
        await self.session.flush()

#
