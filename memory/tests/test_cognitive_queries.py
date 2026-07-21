"""F2-T4: las 7 rutas de la Cognitive Query API responden con datos reales sobre un dataset
de prueba sembrado. "¿Cómo llegué a esto?" ya está cubierta en test_explainability.py
(reutiliza /explain)."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from mindos_common.ids import new_id

from memory.src import main as memory_main
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_thinking_graph import InMemoryThinkingGraph
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding

NOW = datetime.now(timezone.utc)


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


def test_past_thinking_reconstructs_content_as_of_a_date(monkeypatch):
    client = _fresh_client(monkeypatch)

    # v1: idéntica al contenido de búsqueda (para que el mock hashee al mismo vector);
    # MockEmbedding es determinista por texto EXACTO, así que reingerimos el MISMO contenido
    # en la v2 (title distinto) para simular "misma idea, refinada" sin cambiar el hash.
    node_id = _ingest(client, "El límite de conexiones concurrentes es 100.", object_type="fact")
    at_after_ingest = datetime.now(timezone.utc)  # capturado DESPUÉS de crear el nodo, no al importar el módulo

    resp = client.get("/api/v1/cognitive/past-thinking", params={
        "topic": "El límite de conexiones concurrentes es 100.",
        "at": at_after_ingest.isoformat(),
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["topic"] == "El límite de conexiones concurrentes es 100."
    assert len(body["items"]) == 1
    assert body["items"][0]["node_id"] == node_id
    assert body["items"][0]["version"] == 1

    # Antes de que el nodo existiera: no aparece.
    long_ago = (NOW - timedelta(days=3650)).isoformat()
    resp_past = client.get("/api/v1/cognitive/past-thinking", params={
        "topic": "El límite de conexiones concurrentes es 100.", "at": long_ago,
    })
    assert resp_past.json()["items"] == []


def test_similar_filters_by_idea_or_hypothesis_type_and_excludes_self(monkeypatch):
    client = _fresh_client(monkeypatch)

    reference_id = _ingest(client, "Idea: cachear las consultas frecuentes.", object_type="idea")
    similar_idea_id = _ingest(client, "Otra idea sobre caching de consultas.", object_type="idea")
    _ingest(client, "Nota sin relación de tipo idea.", object_type="note")  # no debe aparecer

    resp = client.get("/api/v1/cognitive/similar", params={"node_id": reference_id})
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]

    result_ids = {i["node_id"] for i in items}
    assert reference_id not in result_ids, "no debe incluirse a sí mismo"
    assert similar_idea_id in result_ids
    assert all(i["object_type"] in ("idea", "hypothesis") for i in items)


def test_similar_returns_404_for_unknown_node(monkeypatch):
    client = _fresh_client(monkeypatch)
    assert client.get("/api/v1/cognitive/similar", params={"node_id": str(new_id())}).status_code == 404


def test_decisions_returns_rationale_and_evidence(monkeypatch):
    client = _fresh_client(monkeypatch)

    evidence_id = _ingest(client, "Latencia p99 subió a 800ms bajo carga.", object_type="evidence")
    decision_id = _ingest(
        client, "Escalar el servicio a 3 réplicas.", object_type="decision",
        metadata={"rationale": "La latencia p99 superaba el SLA bajo carga."},
    )
    affected_id = _ingest(client, "Servicio de checkout.", object_type="concept")
    _relate(client, evidence_id, decision_id, "EVIDENCES")
    _relate(client, decision_id, affected_id, "DECIDES")

    resp = client.get("/api/v1/cognitive/decisions", params={"topic": "Escalar el servicio a 3 réplicas."})
    assert resp.status_code == 200, resp.text
    decisions = resp.json()["decisions"]
    assert len(decisions) == 1
    d = decisions[0]
    assert d["node_id"] == decision_id
    assert d["rationale"] == "La latencia p99 superaba el SLA bajo carga."
    assert evidence_id in d["evidence_node_ids"]
    assert affected_id in d["decides_node_ids"]


def test_support_returns_evidence_chain_with_provenance(monkeypatch):
    client = _fresh_client(monkeypatch)

    evidence_id = _ingest(
        client, "Benchmark oficial: 500 req/s.", object_type="evidence",
        source={"kind": "web", "uri": "https://example.com/benchmark"},
    )
    recommendation_id = _ingest(client, "Recomendamos usar este proveedor.", object_type="decision")
    _relate(client, evidence_id, recommendation_id, "SUPPORTS")

    resp = client.get("/api/v1/cognitive/support", params={"node_id": recommendation_id})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["node_id"] == recommendation_id
    assert len(body["support"]) == 1
    assert body["support"][0]["node_id"] == evidence_id
    assert body["support"][0]["source"]["uri"] == "https://example.com/benchmark"


def test_contradictions_lists_pairs(monkeypatch):
    client = _fresh_client(monkeypatch)

    node_a = _ingest(client, "El puerto configurado es 443.", object_type="fact")
    node_b = _ingest(client, "El puerto configurado es 8080.", object_type="fact")
    _relate(client, node_a, node_b, "CONTRADICTS")

    resp = client.get("/api/v1/cognitive/contradictions", params={"topic": "puerto configurado"})
    assert resp.status_code == 200, resp.text
    pairs = resp.json()["contradictions"]
    assert len(pairs) == 1
    ids_in_pair = {pairs[0]["node_a_id"], pairs[0]["node_b_id"]}
    assert ids_in_pair == {node_a, node_b}


def test_patterns_aggregates_by_type_and_period(monkeypatch):
    client = _fresh_client(monkeypatch)

    _ingest(client, "Nota uno.", object_type="note")
    _ingest(client, "Nota dos.", object_type="note")
    _ingest(client, "Idea única.", object_type="idea")

    resp = client.get("/api/v1/cognitive/patterns")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["total_nodes"] == 3
    assert body["most_common_type"] == "note"
    note_bucket = next(b for b in body["buckets"] if b["object_type"] == "note")
    assert note_bucket["count"] == 2
