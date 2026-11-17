"""
F7-T2: las herramientas del asistente personal validan la entrada del modelo antes de ejecutar,
nunca lanzan (un fallo vuelve como resultado de error) y cada una pega en el endpoint real del
Memory Service que le corresponde.
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from agents.src.application.assistant.toolbox import TOOL_SPECS, AssistantToolbox
from agents.src.application.ports.memory_gateway import MemoryGatewayError, MemoryGatewayPort
from agents.src.infrastructure.adapters.http_memory_gateway import HttpMemoryGateway
from memory.src import main as memory_main
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_thinking_graph import InMemoryThinkingGraph
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding


class FakeMemoryGateway(MemoryGatewayPort):
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.ingested: list[dict] = []

    def _maybe_fail(self):
        if self.fail:
            raise MemoryGatewayError("no se pudo contactar al Memory Service (ConnectError)")

    async def search_context(self, query, limit, depth):
        self._maybe_fail()
        if "nada" in query:
            return {"query": query, "fragments": [], "timeline": [], "relations_summary": []}
        return {
            "query": query,
            "fragments": [
                {"node_id": "0193-a", "title": "Decisión: usar Postgres", "content": "Elegimos pgvector.",
                 "object_type": "decision", "score": 0.91, "confidence": 0.8, "importance": 0.7, "via_graph": False},
                {"node_id": "0193-b", "title": "Nota de Traefik", "content": "Puerto 443.",
                 "object_type": "note", "score": 0.6, "confidence": 0.5, "importance": 0.5, "via_graph": True},
            ][:limit],
            "timeline": [], "relations_summary": ["«Nota de Traefik» respalda «Decisión: usar Postgres»"],
        }

    async def ingest(self, payload):
        self._maybe_fail()
        self.ingested.append(payload)
        return {"node_id": "0193-new", "version": 1, "object_type": payload["object_type"], "duplicate_of": None}

    async def decisions(self, topic, limit):
        return {"topic": topic, "decisions": [{"node_id": "0193-a", "title": "Decisión: usar Postgres"}]}

    async def contradictions(self, topic, limit):
        return {"topic": topic, "contradictions": []}

    async def past_thinking(self, topic, at, limit):
        return {"topic": topic, "at": at, "items": []}

    async def explain(self, node_id, max_depth):
        return {"node_id": node_id, "title": "Decisión: usar Postgres", "evidence": []}

    async def history(self, node_id):
        return {"node_id": node_id, "versions": [{"version": 1}, {"version": 2}]}


async def test_search_memory_returns_citable_fragments_and_sources():
    outcome = await AssistantToolbox(FakeMemoryGateway()).execute("search_memory", {"query": "base de datos"})

    assert not outcome.is_error
    assert outcome.summary == "2 fragmentos encontrados"
    payload = json.loads(outcome.content)
    assert [f["title"] for f in payload["fragments"]] == ["Decisión: usar Postgres", "Nota de Traefik"]
    assert payload["fragments"][1]["found_via_graph"] is True
    assert [s["node_id"] for s in outcome.sources] == ["0193-a", "0193-b"]


async def test_search_memory_with_no_results_says_so_instead_of_failing():
    outcome = await AssistantToolbox(FakeMemoryGateway()).execute("search_memory", {"query": "nada de nada"})

    assert not outcome.is_error
    assert outcome.summary == "Sin resultados"
    assert outcome.sources == []


@pytest.mark.parametrize("bad_input", [
    {},                                   # falta `query`
    {"query": ""},                        # vacío
    {"query": "x", "limit": 500},         # fuera de rango
    {"query": ["no", "es", "texto"]},     # tipo equivocado
    "esto no es un objeto",               # el parser tolerante puede entregar cualquier cosa
])
async def test_invalid_model_input_is_rejected_before_touching_memory(bad_input):
    outcome = await AssistantToolbox(FakeMemoryGateway(fail=True)).execute("search_memory", bad_input)

    # `fail=True` haría fallar cualquier llamada real: llegar aquí sin "no respondió" prueba
    # que la validación cortó antes.
    assert outcome.is_error
    assert outcome.summary == "Parámetros inválidos"
    assert "INVALID_INPUT" in outcome.content


async def test_unknown_tool_lists_the_valid_names_so_the_model_can_correct_itself():
    outcome = await AssistantToolbox(FakeMemoryGateway()).execute("borrar_todo", {})

    assert outcome.is_error
    assert all(spec.name in outcome.content for spec in TOOL_SPECS)


async def test_tool_name_differing_only_in_case_is_accepted():
    outcome = await AssistantToolbox(FakeMemoryGateway()).execute("Search_Memory", {"query": "postgres"})
    assert not outcome.is_error


async def test_memory_outage_comes_back_as_an_error_result_not_an_exception():
    outcome = await AssistantToolbox(FakeMemoryGateway(fail=True)).execute("search_memory", {"query": "x"})

    assert outcome.is_error
    assert outcome.summary == "La memoria no respondió"


async def test_save_memory_records_the_owner_as_author_and_the_agent_as_source():
    gateway = FakeMemoryGateway()
    outcome = await AssistantToolbox(gateway, author="Damián").execute("save_memory", {
        "title": "Decisión: Claude Sonnet para el asistente", "content": "Se eligió por latencia y costo.",
        "object_type": "decision", "importance": 0.9,
    })

    assert not outcome.is_error
    assert gateway.ingested == [{
        "object_type": "decision", "title": "Decisión: Claude Sonnet para el asistente",
        "content": "Se eligió por latencia y costo.", "author": "Damián", "importance": 0.9,
        "source": {"kind": "agent", "metadata": {"captured_via": "assistant"}},
    }]
    assert outcome.sources[0]["node_id"] == "0193-new"


def test_tool_definitions_are_stable_and_complete():
    """La lista de herramientas es parte del prefijo cacheado: nombres únicos y esquema cerrado."""
    names = [spec.name for spec in TOOL_SPECS]
    assert len(names) == len(set(names))
    for spec in TOOL_SPECS:
        assert spec.input_schema["type"] == "object"
        assert set(spec.input_schema["required"]) <= set(spec.input_schema["properties"])
        assert len(spec.description) > 80, f"{spec.name}: la descripción es lo único que guía al modelo"


# --- Contra el Memory Service real (en memoria, vía ASGI): cada herramienta pega en una ruta
# que existe y entiende su respuesta. Es lo que detecta un cambio de contrato entre servicios. ---

class _NoopBus:
    async def publish(self, *args, **kwargs):
        return "0-1"

    async def close(self):
        pass


@pytest.fixture
def real_toolbox(monkeypatch):
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", InMemoryDatabase())
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    monkeypatch.setattr(memory_main, "in_memory_thinking_graph", InMemoryThinkingGraph())
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=memory_main.app), base_url="http://memory")
    return AssistantToolbox(HttpMemoryGateway("http://memory", client), author="tester")


async def test_every_tool_works_against_the_real_memory_service(real_toolbox):
    saved = await real_toolbox.execute("save_memory", {
        "title": "Decisión: Postgres con pgvector",
        "content": "Elegimos PostgreSQL con pgvector para no operar una base vectorial aparte.",
        "object_type": "decision",
    })
    assert not saved.is_error, saved.content
    node_id = json.loads(saved.content)["node_id"]

    found = await real_toolbox.execute("search_memory", {"query": "PostgreSQL con pgvector", "limit": 3})
    assert not found.is_error, found.content
    assert node_id in [s["node_id"] for s in found.sources]

    history = await real_toolbox.execute("get_history", {"node_id": node_id})
    assert not history.is_error, history.content
    assert history.summary == "1 versión"

    for tool, tool_input in [
        ("list_decisions", {"topic": "base de datos"}),
        ("find_contradictions", {"topic": "base de datos"}),
        ("recall_past_thinking", {"topic": "base de datos", "at": datetime.now(timezone.utc).isoformat()}),
        ("explain_knowledge", {"node_id": node_id}),
    ]:
        outcome = await real_toolbox.execute(tool, tool_input)
        assert not outcome.is_error, f"{tool}: {outcome.content}"
        json.loads(outcome.content)  # el modelo recibe JSON válido


async def test_unknown_node_id_is_reported_clearly(real_toolbox):
    outcome = await real_toolbox.execute("get_history", {"node_id": str(uuid4())})

    assert outcome.is_error
    assert "no existe un nodo" in outcome.content
