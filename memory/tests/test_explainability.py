"""F2-T3: para una conclusión generada por un agente, /explain devuelve las evidencias y
decisiones que la sustentan, con trazabilidad hasta las fuentes originales."""
from fastapi.testclient import TestClient
from mindos_common.ids import new_id

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


def _fresh_client(monkeypatch):
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", InMemoryDatabase())
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    monkeypatch.setattr(memory_main, "in_memory_thinking_graph", InMemoryThinkingGraph())
    return TestClient(memory_main.app)


def _ingest(client, content, object_type="note", **extra):
    resp = client.post("/api/v1/memory/ingest", json={
        "object_type": object_type, "title": content[:30], "content": content,
        "author": "damian", **extra,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["node_id"]


def _relate(client, source_id, target_id, relation_type):
    resp = client.post("/api/v1/memory/relation", json={
        "source_id": source_id, "target_id": target_id, "relation_type": relation_type,
    })
    assert resp.status_code == 200, resp.text


def test_explain_returns_direct_evidence_with_provenance(monkeypatch):
    client = _fresh_client(monkeypatch)

    evidence_id = _ingest(
        client, "Prueba de carga: 500 req/s sostenidos.", object_type="evidence",
        source={"kind": "pdf", "uri": "file:///loadtest.pdf"},
    )
    decision_id = _ingest(client, "Decidimos escalar a 3 réplicas.", object_type="decision")
    _relate(client, evidence_id, decision_id, "EVIDENCES")

    resp = client.get(f"/api/v1/thinking/explain/{decision_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["node_id"] == decision_id
    assert len(body["supporting_evidence"]) == 1
    ev = body["supporting_evidence"][0]
    assert ev["node_id"] == evidence_id
    assert ev["relation_type"] == "EVIDENCES"
    assert ev["source"] is not None, "la trazabilidad debe llegar hasta la fuente original"
    assert ev["source"]["kind"] == "pdf"
    assert ev["source"]["uri"] == "file:///loadtest.pdf"


def test_explain_nests_multi_level_evidence_chain(monkeypatch):
    """A evidencia a B, B evidencia a C: explain(C) debe anidar A dentro de B."""
    client = _fresh_client(monkeypatch)

    node_a = _ingest(client, "Métricas crudas del monitoreo.", object_type="observation")
    node_b = _ingest(client, "Hipótesis: hay una fuga de memoria.", object_type="hypothesis")
    node_c = _ingest(client, "Decisión: reiniciar el servicio semanalmente.", object_type="decision")
    _relate(client, node_a, node_b, "EVIDENCES")
    _relate(client, node_b, node_c, "DECIDES")

    resp = client.get(f"/api/v1/thinking/explain/{node_c}")
    body = resp.json()

    assert len(body["supporting_evidence"]) == 1
    level1 = body["supporting_evidence"][0]
    assert level1["node_id"] == node_b
    assert level1["relation_type"] == "DECIDES"
    assert len(level1["supporting"]) == 1
    level2 = level1["supporting"][0]
    assert level2["node_id"] == node_a
    assert level2["relation_type"] == "EVIDENCES"


def test_explain_ignores_irrelevant_relation_types(monkeypatch):
    """RELATED_TO/DUPLICATE_OF no cuentan como 'sustento' de una conclusión."""
    client = _fresh_client(monkeypatch)

    node_a = _ingest(client, "Nota relacionada sin valor probatorio.")
    node_b = _ingest(client, "Conclusión bajo análisis.", object_type="decision")
    _relate(client, node_a, node_b, "RELATED_TO")

    resp = client.get(f"/api/v1/thinking/explain/{node_b}")
    assert resp.json()["supporting_evidence"] == []


def test_explain_includes_episodes_that_cited_the_node(monkeypatch):
    client = _fresh_client(monkeypatch)
    node_id = _ingest(client, "Config de Traefik: puerto 443.")

    episode_id = str(new_id())
    client.post("/api/v1/thinking/episodes", json={
        "episode_id": episode_id, "goal": "Encontrar el puerto", "correlation_id": episode_id,
        "agent": "AgentsService",
    })
    client.post(f"/api/v1/thinking/episodes/{episode_id}/steps", json={
        "step_id": str(new_id()), "step_index": 0, "kind": "plan",
        "input": "in", "output": "out", "knowledge_refs": [node_id],
    })
    client.post(f"/api/v1/thinking/episodes/{episode_id}/close", json={
        "status": "completed", "final_output": "El puerto es 443",
    })

    resp = client.get(f"/api/v1/thinking/explain/{node_id}")
    body = resp.json()
    assert len(body["episodes"]) == 1
    assert body["episodes"][0]["id"] == episode_id
    assert body["episodes"][0]["final_output"] == "El puerto es 443"


def test_explain_episode_narrates_steps_in_order(monkeypatch):
    client = _fresh_client(monkeypatch)
    episode_id = str(new_id())

    client.post("/api/v1/thinking/episodes", json={
        "episode_id": episode_id, "goal": "Meta narrada", "correlation_id": episode_id,
        "agent": "AgentsService",
    })
    client.post(f"/api/v1/thinking/episodes/{episode_id}/steps", json={
        "step_id": str(new_id()), "step_index": 0, "kind": "plan",
        "input": "in", "output": "2 pasos generados",
    })
    client.post(f"/api/v1/thinking/episodes/{episode_id}/steps", json={
        "step_id": str(new_id()), "step_index": 1, "kind": "execute",
        "input": "in", "output": "Encontrado", "capability_name": "search_knowledge",
    })
    client.post(f"/api/v1/thinking/episodes/{episode_id}/steps", json={
        "step_id": str(new_id()), "step_index": 2, "kind": "review",
        "input": "in", "output": "Aprobado", "approved": True,
    })
    client.post(f"/api/v1/thinking/episodes/{episode_id}/close", json={
        "status": "completed", "final_output": "Listo",
    })

    resp = client.get(f"/api/v1/thinking/explain/episode/{episode_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["episode"]["id"] == episode_id
    narrative = body["narrative"]
    assert any("Meta narrada" in line for line in narrative)
    assert any("Planificación" in line for line in narrative)
    assert any("search_knowledge" in line for line in narrative)
    assert any("Aprobado" in line for line in narrative)
    assert any("Listo" in line for line in narrative)


def test_explain_returns_404_for_unknown_node_or_episode(monkeypatch):
    client = _fresh_client(monkeypatch)
    assert client.get(f"/api/v1/thinking/explain/{new_id()}").status_code == 404
    assert client.get(f"/api/v1/thinking/explain/episode/{new_id()}").status_code == 404
