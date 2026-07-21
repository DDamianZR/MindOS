"""
F2-T2 (integración): ejecutar un goal a través del endpoint real de Agents deja un episodio
con N pasos persistido en un Memory Service real (in-process, sin red), con `knowledge_refs`
que apuntan a nodos reales usados, y el `final_output` queda ligado a evidencias (nodo
`outcome` + relaciones `EVIDENCES`).

Usa `httpx.ASGITransport` para conectar el `http_client` compartido de Agents directamente
a la app FastAPI de Memory, sin mocks de handler ni red real — el mismo patrón que
`memory/tests/test_phase1_smoke.py`.
"""
import asyncio

import httpx
from fastapi.testclient import TestClient
from mindos_schemas.capabilities import Capability

from agents.src import main as agents_main
from agents.src.infrastructure.adapters.in_memory_capability_registry import (
    InMemoryCapabilityRegistry,
)
from memory.src import main as memory_main
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_thinking_graph import InMemoryThinkingGraph
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding


class _NoopBus:
    async def publish(self, *args, **kwargs):
        return "0-1"

    async def close(self):
        pass


def test_full_episode_recorded_with_knowledge_refs_and_outcome_evidenced(monkeypatch):
    # 1. Memory Service in-process con estado limpio
    db = InMemoryDatabase()
    thinking_graph = InMemoryThinkingGraph()
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", db)
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    monkeypatch.setattr(memory_main, "in_memory_thinking_graph", thinking_graph)

    memory_client = TestClient(memory_main.app)

    # 2. Sembrar contenido real que el agente deba encontrar y citar
    seed = memory_client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "Config de Traefik",
        "content": "El puerto configurado para TLS es 443.", "author": "damian",
    })
    assert seed.status_code == 201, seed.text
    seeded_node_id = seed.json()["node_id"]

    # 3. Registrar capacidades deterministas para el plan fijo de MockLlm (search_knowledge +
    # send_chat_message): 'communication' no resuelve a URL conocida -> Executor simula limpio.
    registry = InMemoryCapabilityRegistry()
    monkeypatch.setattr(agents_main, "capability_registry", registry)

    async def _register():
        await registry.register([
            Capability(
                name="search_knowledge", description="Busca en memoria",
                parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                provider_service="memory", endpoint_path="/api/v1/memory/search",
            ),
            Capability(
                name="send_chat_message", description="Envía un mensaje", parameters_schema={},
                provider_service="communication", endpoint_path="/api/v1/communication/send",
            ),
        ])
    asyncio.run(_register())

    # 4. Redirigir el http_client compartido de Agents hacia el MISMO Memory Service in-process.
    async def override_http_client():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=memory_main.app)) as client:
            yield client
    agents_main.app.dependency_overrides[agents_main.get_http_client] = override_http_client

    agents_client = TestClient(agents_main.app)
    try:
        resp = agents_client.post("/api/v1/agents/execute", params={"goal": "puerto configurado para TLS"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        correlation_id = body["correlation_id"]
    finally:
        agents_main.app.dependency_overrides.clear()

    # 5. El episodio quedó persistido en Memory: cerrado, con varios pasos, knowledge_refs reales.
    episode_resp = memory_client.get(f"/api/v1/thinking/episodes/{correlation_id}")
    assert episode_resp.status_code == 200, episode_resp.text
    episode = episode_resp.json()

    assert episode["status"] == "completed"
    assert episode["ended_at"] is not None
    assert len(episode["steps"]) >= 3, "se esperan al menos plan + execute + review"

    plan_step = next(s for s in episode["steps"] if s["kind"] == "plan")
    assert seeded_node_id in plan_step["knowledge_refs"], (
        "el paso de planificación debe citar el nodo real recuperado como contexto"
    )

    # 6. El resultado final quedó promovido a conocimiento ('outcome'), evidenciado por el
    # nodo sembrado (DoD: "el final_output queda ligado a las evidencias").
    neighbors = memory_client.get(f"/api/v1/memory/node/{seeded_node_id}/neighbors")
    assert neighbors.status_code == 200
    evidences_edges = [
        n for n in neighbors.json()["neighbors"]
        if n["source_id"] == seeded_node_id and n["relation_type"] == "EVIDENCES"
    ]
    assert len(evidences_edges) == 1, "el nodo sembrado debe evidenciar exactamente un outcome"

    outcome_node_id = evidences_edges[0]["target_id"]
    outcome_history = memory_client.get(f"/api/v1/memory/node/{outcome_node_id}/history")
    assert outcome_history.status_code == 200
    assert outcome_history.json()["object_type"] == "outcome"
