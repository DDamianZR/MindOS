"""F4-T2: MindOSClient habla siempre a través del Gateway (F3-T1), nunca directo con
Memory/Agents — verifica que cada método construye la URL/params/headers correctos."""
import json

import httpx
import pytest
from mindos_mcp.mindos_client import MindOSClient


def _client(handler):
    return MindOSClient(
        "http://gateway:8000", "test-key", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_search_calls_the_gateway_memory_search_endpoint_with_api_key():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"query": "puerto", "results": []})

    client = _client(handler)
    result = await client.search("puerto configurado", limit=3)

    assert len(calls) == 1
    req = calls[0]
    assert req.url.path == "/api/v1/memory/search"
    assert dict(req.url.params) == {"query": "puerto configurado", "limit": "3"}
    assert req.headers["X-Api-Key"] == "test-key"
    assert result == {"query": "puerto", "results": []}


@pytest.mark.asyncio
async def test_ingest_sends_source_kind_agent_with_the_given_raw_ref():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(201, json={"node_id": "x", "version": 1})

    client = _client(handler)
    await client.ingest(title="T", content="C", object_type="idea", source="conversación X")

    payload = json.loads(calls[0].content)
    assert payload["object_type"] == "idea"
    assert payload["title"] == "T"
    assert payload["content"] == "C"
    assert payload["source"] == {"kind": "agent", "raw_ref": "conversación X"}


@pytest.mark.asyncio
async def test_context_posts_query_limit_depth_as_json_body():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"fragments": []})

    client = _client(handler)
    await client.context("puerto de traefik", limit=4, depth=2)

    assert calls[0].url.path == "/api/v1/memory/context"
    assert json.loads(calls[0].content) == {"query": "puerto de traefik", "limit": 4, "depth": 2}


@pytest.mark.asyncio
async def test_explain_calls_the_thinking_explain_endpoint_for_the_given_node():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"node_id": "abc", "supporting_evidence": [], "episodes": []})

    client = _client(handler)
    await client.explain("abc-123", max_depth=5)

    assert calls[0].url.path == "/api/v1/thinking/explain/abc-123"
    assert dict(calls[0].url.params) == {"max_depth": "5"}


@pytest.mark.asyncio
async def test_ask_cognitive_dispatches_to_the_right_endpoint_per_question_type():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={})

    client = _client(handler)
    await client.ask_cognitive("contradictions", {"topic": "puerto"})

    assert calls[0].url.path == "/api/v1/cognitive/contradictions"
    assert dict(calls[0].url.params) == {"topic": "puerto"}


@pytest.mark.asyncio
async def test_ask_cognitive_rejects_an_unknown_question_type_before_any_request():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={})

    client = _client(handler)
    with pytest.raises(ValueError, match="question_type desconocido"):
        await client.ask_cognitive("no_existe", {})
    assert calls == []


@pytest.mark.asyncio
async def test_downstream_http_error_propagates_to_the_caller():
    """Un tool MCP debe poder fallar visiblemente para el LLM que lo invoca, no tragarse el
    error — a diferencia de la resiliencia best-effort del resto del sistema."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Credenciales inválidas o ausentes."})

    client = _client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("algo")
