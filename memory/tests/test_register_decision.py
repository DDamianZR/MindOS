"""F2-T6: registrar una decisión y recuperarla vía /cognitive/decisions con su rationale
y evidencias."""
from fastapi.testclient import TestClient

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


def _ingest(client, content, object_type="note"):
    resp = client.post("/api/v1/memory/ingest", json={
        "object_type": object_type, "title": content[:30], "content": content, "author": "damian",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["node_id"]


def test_register_decision_creates_node_with_rationale_and_relations(monkeypatch):
    client = _fresh_client(monkeypatch)

    evidence_id = _ingest(client, "Latencia p99 subió a 800ms bajo carga.", object_type="evidence")
    project_id = _ingest(client, "Proyecto: servicio de checkout.", object_type="project")

    resp = client.post("/api/v1/cognitive/decision", json={
        "title": "Escalar a 3 réplicas", "content": "Escalar el servicio de checkout a 3 réplicas.",
        "rationale": "La latencia p99 superaba el SLA acordado bajo carga.", "author": "damian",
        "evidence_node_ids": [evidence_id], "affected_node_ids": [project_id],
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    decision_id = body["node_id"]
    assert body["version"] == 1
    assert body["rationale"] == "La latencia p99 superaba el SLA acordado bajo carga."

    # La relación EVIDENCES: evidence_id -> decision_id
    neighbors_evidence = client.get(f"/api/v1/memory/node/{evidence_id}/neighbors").json()["neighbors"]
    assert any(
        n["target_id"] == decision_id and n["relation_type"] == "EVIDENCES" for n in neighbors_evidence
    )

    # La relación DECIDES: decision_id -> project_id
    neighbors_decision = client.get(f"/api/v1/memory/node/{decision_id}/neighbors").json()["neighbors"]
    assert any(
        n["target_id"] == project_id and n["relation_type"] == "DECIDES" for n in neighbors_decision
    )


def test_registered_decision_is_recoverable_via_cognitive_decisions(monkeypatch):
    client = _fresh_client(monkeypatch)
    evidence_id = _ingest(client, "Benchmark: 500 req/s sostenidos.", object_type="evidence")

    resp = client.post("/api/v1/cognitive/decision", json={
        "title": "Migrar a Traefik", "content": "Migrar el proxy reverso a Traefik.",
        "rationale": "Soporte nativo de Let's Encrypt reduce el trabajo operativo.", "author": "damian",
        "evidence_node_ids": [evidence_id],
    })
    decision_id = resp.json()["node_id"]

    list_resp = client.get("/api/v1/cognitive/decisions", params={"topic": "Migrar el proxy reverso a Traefik."})
    assert list_resp.status_code == 200, list_resp.text
    decisions = list_resp.json()["decisions"]
    assert len(decisions) == 1
    d = decisions[0]
    assert d["node_id"] == decision_id
    assert d["rationale"] == "Soporte nativo de Let's Encrypt reduce el trabajo operativo."
    assert evidence_id in d["evidence_node_ids"]


def test_register_decision_without_relations_still_works(monkeypatch):
    """evidence_node_ids/affected_node_ids son opcionales."""
    client = _fresh_client(monkeypatch)
    resp = client.post("/api/v1/cognitive/decision", json={
        "title": "Decisión simple", "content": "Contenido de la decisión.",
        "rationale": "Rationale mínimo.", "author": "damian",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["rationale"] == "Rationale mínimo."
