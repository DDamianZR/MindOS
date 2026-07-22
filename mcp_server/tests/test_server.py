"""
F4-T2: las 5 tools quedan registradas con el nombre esperado en el servidor FastMCP real, y
cada función decorada sigue siendo invocable directamente (el decorador `@mcp.tool` de FastMCP
devuelve la función original sin envolver) — se prueba la unión completa server+tools+client
monkeypencheando el `client` a nivel de módulo, sin mocks de transporte MCP.
"""
import pytest
from mindos_mcp import server


@pytest.mark.asyncio
async def test_all_five_tools_are_registered_with_their_mindos_names():
    registered = {tool.name for tool in await server.mcp.list_tools()}
    assert registered == {
        "mindos_search", "mindos_ingest", "mindos_context", "mindos_ask_cognitive", "mindos_explain",
    }


@pytest.mark.asyncio
async def test_mindos_search_tool_function_delegates_to_the_module_level_client(monkeypatch):
    calls = []

    class _FakeClient:
        async def search(self, query, limit=5):
            calls.append((query, limit))
            return {"results": [{"node_id": "n1", "content": "El puerto es 443"}]}

    monkeypatch.setattr(server, "client", _FakeClient())
    result = await server.mindos_search("puerto configurado", limit=2)

    assert calls == [("puerto configurado", 2)]
    assert result["results"][0]["node_id"] == "n1"


@pytest.mark.asyncio
async def test_mindos_explain_tool_function_delegates_to_the_module_level_client(monkeypatch):
    calls = []

    class _FakeClient:
        async def explain(self, node_id, max_depth=3):
            calls.append((node_id, max_depth))
            return {"node_id": node_id, "supporting_evidence": [], "episodes": []}

    monkeypatch.setattr(server, "client", _FakeClient())
    result = await server.mindos_explain("node-42")

    assert calls == [("node-42", 3)]
    assert result["node_id"] == "node-42"


def test_health_route_is_registered_and_public():
    paths = {route.path for route in server.mcp._custom_starlette_routes}
    assert "/health" in paths
