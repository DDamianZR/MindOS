from abc import ABC, abstractmethod
from typing import Any


class MemoryGatewayError(Exception):
    """El Memory Service no pudo atender la operación (caído, 4xx/5xx, respuesta inválida)."""


class MemoryGatewayPort(ABC):
    """
    Puerto hacia el Knowledge Graph / Thinking Graph tal como lo necesita el asistente personal
    (F7-T2). Cada método devuelve el JSON ya decodificado del Memory Service; el adaptador se
    encarga del transporte. Cualquier fallo sale como `MemoryGatewayError`.
    """

    @abstractmethod
    async def search_context(self, query: str, limit: int, depth: int) -> dict[str, Any]:
        """Contexto GraphRAG citable para una consulta (Context Builder v2, F1-T7)."""

    @abstractmethod
    async def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Guarda un Objeto Cognitivo nuevo (o una versión nueva de uno existente)."""

    @abstractmethod
    async def decisions(self, topic: str, limit: int) -> dict[str, Any]:
        """Decisiones registradas sobre un tema, con su porqué."""

    @abstractmethod
    async def contradictions(self, topic: str, limit: int) -> dict[str, Any]:
        """Contradicciones detectadas en el conocimiento sobre un tema."""

    @abstractmethod
    async def past_thinking(self, topic: str, at: str, limit: int) -> dict[str, Any]:
        """Lo que se pensaba sobre un tema en un instante pasado."""

    @abstractmethod
    async def explain(self, node_id: str, max_depth: int) -> dict[str, Any]:
        """Cadena de evidencias y razonamiento que sustenta un nodo."""

    @abstractmethod
    async def history(self, node_id: str) -> dict[str, Any]:
        """Historial de versiones de un nodo."""
