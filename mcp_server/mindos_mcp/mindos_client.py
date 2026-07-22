from typing import Any

import httpx

# Mapa question_type -> ruta /cognitive/* (F2-T4). "explain" no está aquí a propósito: es su
# propia tool MCP dedicada (mindos_explain), no una de las 7 preguntas de este despachador.
_COGNITIVE_ENDPOINTS = {
    "past_thinking": "/api/v1/cognitive/past-thinking",
    "similar": "/api/v1/cognitive/similar",
    "decisions": "/api/v1/cognitive/decisions",
    "support": "/api/v1/cognitive/support",
    "contradictions": "/api/v1/cognitive/contradictions",
    "patterns": "/api/v1/cognitive/patterns",
}


class MindOSClient:
    """
    Cliente hacia MindOS a través del Gateway (F3-T1) — la misma puerta que usaría cualquier
    otro cliente externo. Nunca habla directo con Memory/Agents: ni siquiera el servidor MCP,
    que corre en el mismo stack, se salta el único punto de entrada seguro.
    """
    def __init__(self, base_url: str, api_key: str, http_client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = http_client or httpx.AsyncClient(timeout=30.0)

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self.api_key} if self.api_key else {}

    async def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        resp = await self._client.post(
            f"{self.base_url}/api/v1/memory/search", params={"query": query, "limit": limit},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def ingest(
        self, title: str, content: str, object_type: str = "note", source: str | None = None,
        author: str = "mcp-client",
    ) -> dict[str, Any]:
        payload = {
            "object_type": object_type, "title": title, "content": content, "author": author,
            # kind="agent" siempre (F1-T2 provenance): esta captura vino de un asistente de IA
            # externo vía MCP, no de un humano tecleando directo — `source` (libre) es la pista
            # de dónde salió dentro de esa conversación, si el llamador la da.
            "source": {"kind": "agent", "raw_ref": source},
        }
        resp = await self._client.post(
            f"{self.base_url}/api/v1/memory/ingest", json=payload, headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def context(self, query: str, limit: int = 5, depth: int = 1) -> dict[str, Any]:
        resp = await self._client.post(
            f"{self.base_url}/api/v1/memory/context",
            json={"query": query, "limit": limit, "depth": depth}, headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def explain(self, node_id: str, max_depth: int = 3) -> dict[str, Any]:
        resp = await self._client.get(
            f"{self.base_url}/api/v1/thinking/explain/{node_id}", params={"max_depth": max_depth},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def ask_cognitive(self, question_type: str, params: dict[str, Any]) -> dict[str, Any]:
        path = _COGNITIVE_ENDPOINTS.get(question_type)
        if not path:
            valid = ", ".join(sorted(_COGNITIVE_ENDPOINTS))
            raise ValueError(f"question_type desconocido: {question_type!r}. Válidos: {valid}.")
        resp = await self._client.get(f"{self.base_url}{path}", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()
