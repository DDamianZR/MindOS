import math
from typing import Any

from memory.src.application.ports.vector_store import VectorSearchResult, VectorStorePort


class InMemoryVectorStore(VectorStorePort):
    """
    Implementación en memoria de VectorStorePort para simulación y pruebas del Kernel.
    Realiza una búsqueda de similitud coseno real sobre los vectores en memoria.
    """
    def __init__(self):
        self._vectors: dict[str, dict[str, Any]] = {}

    async def upsert(self, vector_id: str, embedding: list[float], payload: dict[str, Any]) -> None:
        self._vectors[vector_id] = {
            "embedding": embedding,
            "payload": payload
        }

    async def search(
        self,
        query_embedding: list[float],
        limit: int,
        filters: dict[str, Any] | None = None
    ) -> list[VectorSearchResult]:
        results = []

        for vid, data in self._vectors.items():
            emb = data["embedding"]
            payload = data["payload"]

            # Aplicar filtros simples si se proveen (ej: buscar coincidencias exactas en el payload)
            if filters:
                match = True
                for k, v in filters.items():
                    if payload.get(k) != v:
                        match = False
                        break
                if not match:
                    continue

            # Calcular similitud coseno
            score = self._cosine_similarity(query_embedding, emb)
            results.append(VectorSearchResult(id=vid, score=score, payload=payload))

        # Ordenar por score descendente y aplicar límite
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def _cosine_similarity(self, v1: list[float], v2: list[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(v1, v2, strict=False))
        magnitude_v1 = math.sqrt(sum(a * a for a in v1))
        magnitude_v2 = math.sqrt(sum(b * b for b in v2))

        if magnitude_v1 == 0.0 or magnitude_v2 == 0.0:
            return 0.0

        return dot_product / (magnitude_v1 * magnitude_v2)
