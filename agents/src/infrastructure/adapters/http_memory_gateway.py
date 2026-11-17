from typing import Any

import httpx
from mindos_common.context import get_correlation_id

from agents.src.application.ports.memory_gateway import MemoryGatewayError, MemoryGatewayPort


class HttpMemoryGateway(MemoryGatewayPort):
    """Adaptador HTTP de `MemoryGatewayPort` contra el Memory Service (F7-T2)."""

    def __init__(self, base_url: str, http_client: httpx.AsyncClient):
        self._base_url = base_url.rstrip("/")
        self._http = http_client

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        correlation_id = get_correlation_id()
        headers = {"X-Correlation-Id": str(correlation_id)} if correlation_id else {}
        try:
            response = await self._http.request(method, f"{self._base_url}{path}", headers=headers, **kwargs)
        except httpx.RequestError as e:
            raise MemoryGatewayError(f"no se pudo contactar al Memory Service ({type(e).__name__})") from e

        if response.status_code == 404:
            raise MemoryGatewayError("no existe un nodo con ese identificador")
        if response.status_code >= 400:
            detail = response.text[:300]
            raise MemoryGatewayError(f"el Memory Service respondió {response.status_code}: {detail}")
        try:
            return response.json()
        except ValueError as e:
            raise MemoryGatewayError("el Memory Service devolvió una respuesta que no es JSON") from e

    async def search_context(self, query: str, limit: int, depth: int) -> dict[str, Any]:
        return await self._request(
            "POST", "/api/v1/memory/context", json={"query": query, "limit": limit, "depth": depth}
        )

    async def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/memory/ingest", json=payload)

    async def decisions(self, topic: str, limit: int) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/cognitive/decisions", params={"topic": topic, "limit": limit})

    async def contradictions(self, topic: str, limit: int) -> dict[str, Any]:
        return await self._request(
            "GET", "/api/v1/cognitive/contradictions", params={"topic": topic, "limit": limit}
        )

    async def past_thinking(self, topic: str, at: str, limit: int) -> dict[str, Any]:
        return await self._request(
            "GET", "/api/v1/cognitive/past-thinking", params={"topic": topic, "at": at, "limit": limit}
        )

    async def explain(self, node_id: str, max_depth: int) -> dict[str, Any]:
        return await self._request(
            "GET", f"/api/v1/thinking/explain/{node_id}", params={"max_depth": max_depth}
        )

    async def history(self, node_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/memory/node/{node_id}/history")
