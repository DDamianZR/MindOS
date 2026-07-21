"""
Cierre de Fase 2 — verificación integral end-to-end (plan/02-thinking-graph.md):
"en este punto MindOS ya se siente como la visión aunque no tenga dashboard ni WhatsApp:
responde las 7 preguntas y explica su razonamiento por API."

Dos flujos:
1. Un agente real (Agents + Memory in-process vía ASGITransport, como en
   test_reasoning_trace_integration.py) deja un episodio explicable: /explain sobre el
   'outcome' que produjo muestra la evidencia y el episodio que lo originó.
2. Sobre un dataset sembrado, las 7 preguntas insignia responden con datos reales:
   past-thinking, cómo-llegué-a-esto (/explain), similar, decisions, support,
   contradictions, patterns.
"""
import asyncio
from datetime import datetime, timezone

import httpx
from fastapi.testclient import TestClient
from mindos_schemas.capabilities import Capability

from agents.src import main as agents_main
from agents.src.infrastructure.adapters.in_memory_capability_registry import (
    InMemoryCapabilityRegistry,
)
from memory.src import main as memory_main
from memory.src.application.ports.llm import LlmPort
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_thinking_graph import InMemoryThinkingGraph
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding


class _NoopBus:
    async def publish(self, *args, **kwargs):
        return "0-1"

    async def close(self):
        pass


class _AlwaysContradictsLlm(LlmPort):
    """Test double determinista para la parte de contradicciones del smoke."""
    async def generate(self, prompt, system_instruction=None, json_mode=False):
        return '{"contradicts": true, "rationale": "Valores incompatibles para el mismo hecho.", "confidence": 0.85}'

    async def chat(self, messages, json_mode=False):
        return await self.generate(messages[-1]["content"] if messages else "")


def _patch_memory(monkeypatch, llm=None):
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "llm_provider", llm or _AlwaysContradictsLlm())
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", InMemoryDatabase())
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    monkeypatch.setattr(memory_main, "in_memory_thinking_graph", InMemoryThinkingGraph())
    monkeypatch.setattr(memory_main.settings, "CONTRADICTION_SIMILARITY_THRESHOLD", 0.0)


def test_phase2_agent_episode_is_explainable(monkeypatch):
    """Un agente real deja un episodio; /explain sobre su 'outcome' muestra evidencia + episodio."""
    _patch_memory(monkeypatch)
    memory_client = TestClient(memory_main.app)

    seed = memory_client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "Config de Traefik",
        "content": "El puerto configurado para TLS es 443.", "author": "damian",
    })
    assert seed.status_code == 201, seed.text
    seeded_node_id = seed.json()["node_id"]

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

    async def override_http_client():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=memory_main.app)) as client:
            yield client
    agents_main.app.dependency_overrides[agents_main.get_http_client] = override_http_client

    agents_client = TestClient(agents_main.app)
    try:
        resp = agents_client.post("/api/v1/agents/execute", params={"goal": "puerto configurado para TLS"})
        assert resp.status_code == 200, resp.text
        correlation_id = resp.json()["correlation_id"]
    finally:
        agents_main.app.dependency_overrides.clear()

    # El episodio quedó persistido y cerrado.
    episode = memory_client.get(f"/api/v1/thinking/episodes/{correlation_id}").json()
    assert episode["status"] == "completed"

    # El outcome quedó evidenciado por el nodo sembrado; /explain lo reconstruye.
    neighbors = memory_client.get(f"/api/v1/memory/node/{seeded_node_id}/neighbors").json()["neighbors"]
    evidences = [n for n in neighbors if n["relation_type"] == "EVIDENCES"]
    assert len(evidences) == 1
    outcome_node_id = evidences[0]["target_id"]

    explain = memory_client.get(f"/api/v1/thinking/explain/{outcome_node_id}")
    assert explain.status_code == 200, explain.text
    explain_body = explain.json()
    assert any(e["node_id"] == seeded_node_id for e in explain_body["supporting_evidence"])
    assert any(ep["id"] == correlation_id for ep in explain_body["episodes"])


def test_phase2_seven_cognitive_questions_respond_with_real_data(monkeypatch):
    """Sobre un dataset sembrado, las 7 preguntas insignia responden con datos reales."""
    _patch_memory(monkeypatch)
    client = TestClient(memory_main.app)

    def ingest(content, object_type="note", **extra):
        r = client.post("/api/v1/memory/ingest", json={
            "object_type": object_type, "title": content[:30], "content": content,
            "author": "damian", **extra,
        })
        assert r.status_code == 201, r.text
        return r.json()["node_id"]

    def relate(source_id, target_id, relation_type):
        r = client.post("/api/v1/memory/relation", json={
            "source_id": source_id, "target_id": target_id, "relation_type": relation_type,
        })
        assert r.status_code == 200, r.text

    # --- Dataset ---
    idea_id = ingest("Idea: cachear las consultas frecuentes de reportes.", object_type="idea")
    ingest("Otra idea sobre cachear resultados de reportes.", object_type="idea")

    evidence_id = ingest("Latencia p99 subió a 800ms bajo carga.", object_type="evidence")
    decision_id = ingest(
        "Escalar el servicio a 3 réplicas.", object_type="decision",
        metadata={"rationale": "La latencia p99 superaba el SLA bajo carga."},
    )
    relate(evidence_id, decision_id, "EVIDENCES")

    fact_a = ingest("El puerto configurado es 443.", object_type="fact")
    fact_b = ingest("El puerto configurado es 8080.", object_type="fact")

    # 1. ¿Qué pensaba en esta fecha sobre X? (past-thinking)
    resp = client.get("/api/v1/cognitive/past-thinking", params={
        "topic": "Idea: cachear las consultas frecuentes de reportes.",
        "at": datetime.now(timezone.utc).isoformat(),
    })
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1

    # 2. ¿Cómo llegué a esta conclusión? (/explain, reusa F2-T3)
    resp = client.get(f"/api/v1/thinking/explain/{decision_id}")
    assert resp.status_code == 200
    assert len(resp.json()["supporting_evidence"]) == 1

    # 3. ¿Qué ideas similares tuve antes? (similar)
    resp = client.get("/api/v1/cognitive/similar", params={"node_id": idea_id})
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1

    # 4. ¿Qué decisiones tomé y por qué? (decisions)
    resp = client.get("/api/v1/cognitive/decisions", params={"topic": "Escalar el servicio a 3 réplicas."})
    assert resp.status_code == 200
    decisions = resp.json()["decisions"]
    assert len(decisions) == 1
    assert decisions[0]["rationale"]

    # 5. ¿Qué respalda esta recomendación? (support)
    resp = client.get("/api/v1/cognitive/support", params={"node_id": decision_id})
    assert resp.status_code == 200
    assert len(resp.json()["support"]) == 1

    # 6. ¿Qué contradicciones existen? (contradictions — ya detectadas on-ingest arriba)
    resp = client.get("/api/v1/cognitive/contradictions", params={"topic": "puerto configurado"})
    assert resp.status_code == 200
    pairs = resp.json()["contradictions"]
    assert len(pairs) == 1
    assert {pairs[0]["node_a_id"], pairs[0]["node_b_id"]} == {fact_a, fact_b}

    # 7. ¿Qué patrones aparecen en mi forma de pensar? (patterns)
    resp = client.get("/api/v1/cognitive/patterns")
    assert resp.status_code == 200
    assert resp.json()["total_nodes"] >= 6
