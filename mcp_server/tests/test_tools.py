"""F4-T2: la lógica de cada tool delega en MindOSClient con los argumentos correctos —
probado con un cliente falso, sin red ni FastMCP de por medio."""
import pytest
from mindos_mcp import tools


class _FakeClient:
    def __init__(self):
        self.calls: list[tuple] = []

    async def search(self, query, limit=5):
        self.calls.append(("search", query, limit))
        return {"results": []}

    async def ingest(self, title, content, object_type="note", source=None):
        self.calls.append(("ingest", title, content, object_type, source))
        return {"node_id": "x"}

    async def context(self, query, limit=5, depth=1):
        self.calls.append(("context", query, limit, depth))
        return {"fragments": []}

    async def ask_cognitive(self, question_type, params):
        self.calls.append(("ask_cognitive", question_type, params))
        return {}

    async def explain(self, node_id, max_depth=3):
        self.calls.append(("explain", node_id, max_depth))
        return {"node_id": node_id}


@pytest.mark.asyncio
async def test_search_delegates_with_the_given_query_and_limit():
    client = _FakeClient()
    result = await tools.search(client, "puerto configurado", limit=7)
    assert client.calls == [("search", "puerto configurado", 7)]
    assert result == {"results": []}


@pytest.mark.asyncio
async def test_ingest_delegates_with_all_fields():
    client = _FakeClient()
    await tools.ingest(client, title="T", content="C", object_type="fact", source="chat")
    assert client.calls == [("ingest", "T", "C", "fact", "chat")]


@pytest.mark.asyncio
async def test_ingest_defaults_object_type_to_note_and_source_to_none():
    client = _FakeClient()
    await tools.ingest(client, title="T", content="C")
    assert client.calls == [("ingest", "T", "C", "note", None)]


@pytest.mark.asyncio
async def test_context_delegates_with_query_limit_depth():
    client = _FakeClient()
    await tools.context(client, "puerto", limit=2, depth=3)
    assert client.calls == [("context", "puerto", 2, 3)]


@pytest.mark.asyncio
async def test_ask_cognitive_delegates_question_type_and_params():
    client = _FakeClient()
    await tools.ask_cognitive(client, "decisions", {"topic": "escalado"})
    assert client.calls == [("ask_cognitive", "decisions", {"topic": "escalado"})]


@pytest.mark.asyncio
async def test_explain_delegates_node_id_and_max_depth():
    client = _FakeClient()
    await tools.explain(client, "node-1", max_depth=1)
    assert client.calls == [("explain", "node-1", 1)]
