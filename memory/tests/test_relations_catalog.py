"""F1-T6: catálogo tipado de relaciones. Crear una relación SUPPORTS entre dos nodos y
recuperarla en /neighbors; los tipos fuera del catálogo se normalizan a CUSTOM."""
from fastapi.testclient import TestClient

from memory.src import main as memory_main
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding


class _NoopBus:
    async def publish(self, *args, **kwargs):
        return "0-1"

    async def close(self):
        pass


def _fresh_client(monkeypatch):
    db = InMemoryDatabase()
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", db)
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    return TestClient(memory_main.app), db


def _ingest(client, content):
    resp = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": content[:20], "content": content, "author": "damian",
    })
    return resp.json()["node_id"]


def test_supports_relation_created_and_recoverable_in_neighbors(monkeypatch):
    client, _ = _fresh_client(monkeypatch)
    evidence_node = _ingest(client, "Prueba de carga: 500 req/s sostenidos sin errores.")
    hypothesis_node = _ingest(client, "El servidor soporta al menos 500 req/s.")

    rel = client.post("/api/v1/memory/relation", json={
        "source_id": evidence_node, "target_id": hypothesis_node, "relation_type": "SUPPORTS",
    })
    assert rel.status_code == 200, rel.text
    assert rel.json()["relation_type"] == "SUPPORTS"
    assert rel.json()["custom_relation_type"] is None

    neighbors = client.get(f"/api/v1/memory/node/{evidence_node}/neighbors", params={"depth": 2})
    assert neighbors.status_code == 200, neighbors.text
    body = neighbors.json()
    assert body["node_id"] == evidence_node
    edges = body["neighbors"]
    assert len(edges) == 1
    assert edges[0]["source_id"] == evidence_node
    assert edges[0]["target_id"] == hypothesis_node
    assert edges[0]["relation_type"] == "SUPPORTS"


def test_relation_type_outside_catalog_is_normalized_to_custom(monkeypatch):
    client, _ = _fresh_client(monkeypatch)
    a = _ingest(client, "Empresa Acme Corp")
    b = _ingest(client, "Damian trabaja en Acme")

    rel = client.post("/api/v1/memory/relation", json={
        "source_id": b, "target_id": a, "relation_type": "WORKS_AT",
    })
    assert rel.status_code == 200, rel.text
    body = rel.json()
    assert body["relation_type"] == "CUSTOM"
    assert body["custom_relation_type"] == "WORKS_AT"

    neighbors = client.get(f"/api/v1/memory/node/{b}/neighbors")
    edge = neighbors.json()["neighbors"][0]
    assert edge["relation_type"] == "CUSTOM"
    assert edge["metadata"]["custom_relation_type"] == "WORKS_AT"


def test_neighbors_respects_depth(monkeypatch):
    client, _ = _fresh_client(monkeypatch)
    a = _ingest(client, "Nodo A")
    b = _ingest(client, "Nodo B")
    c = _ingest(client, "Nodo C")

    client.post("/api/v1/memory/relation", json={"source_id": a, "target_id": b, "relation_type": "RELATED_TO"})
    client.post("/api/v1/memory/relation", json={"source_id": b, "target_id": c, "relation_type": "RELATED_TO"})

    depth1 = client.get(f"/api/v1/memory/node/{a}/neighbors", params={"depth": 1}).json()["neighbors"]
    assert {e["target_id"] for e in depth1} == {b}

    depth2 = client.get(f"/api/v1/memory/node/{a}/neighbors", params={"depth": 2}).json()["neighbors"]
    assert {e["target_id"] for e in depth2} == {b, c}


def test_neighbors_includes_incoming_relations_not_just_outgoing(monkeypatch):
    """F4-T1: descubierto al integrar el Grafo del Dashboard -- un nodo que solo RECIBE
    relaciones (p.ej. una decisión con evidencia apuntándole) debe verse conectado en /neighbors
    igual que uno que las origina; antes solo se recorrían las salientes."""
    client, _ = _fresh_client(monkeypatch)
    evidence = _ingest(client, "Evidencia")
    decision = _ingest(client, "Decisión")

    client.post("/api/v1/memory/relation", json={
        "source_id": evidence, "target_id": decision, "relation_type": "EVIDENCES",
    })

    # Sin la arista saliente propia de `decision`, antes del fix esto devolvía una lista vacía.
    neighbors = client.get(f"/api/v1/memory/node/{decision}/neighbors", params={"depth": 1}).json()["neighbors"]
    assert len(neighbors) == 1
    assert neighbors[0]["source_id"] == evidence
    assert neighbors[0]["target_id"] == decision
    assert neighbors[0]["relation_type"] == "EVIDENCES"


def test_neighbors_dedups_edges_found_from_both_directions_in_a_cycle(monkeypatch):
    """En un ciclo (A->B y B->A), la recorrida saliente y la entrante desde A pueden encontrar
    ambas aristas cada una por su lado a depth=2 -- no deben duplicarse en la respuesta."""
    client, _ = _fresh_client(monkeypatch)
    a = _ingest(client, "Nodo A")
    b = _ingest(client, "Nodo B")
    client.post("/api/v1/memory/relation", json={"source_id": a, "target_id": b, "relation_type": "RELATED_TO"})
    client.post("/api/v1/memory/relation", json={"source_id": b, "target_id": a, "relation_type": "RELATED_TO"})

    neighbors = client.get(f"/api/v1/memory/node/{a}/neighbors", params={"depth": 2}).json()["neighbors"]
    pairs = [(e["source_id"], e["target_id"]) for e in neighbors]
    assert sorted(pairs) == sorted([(a, b), (b, a)])
