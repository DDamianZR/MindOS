"""F1-T1: el Objeto Cognitivo rico (object_type, confidence, importance, status, evidence)
debe persistir y recuperarse correctamente, tanto en la respuesta de ingesta como en la
búsqueda y el historial (los tres caminos de lectura del Memory Service)."""
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


def _ingest_rich_hypothesis(monkeypatch, db, vector_store):
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", db)
    monkeypatch.setattr(memory_main, "in_memory_vector_store", vector_store)

    client = TestClient(memory_main.app)
    resp = client.post("/api/v1/memory/ingest", json={
        "object_type": "hypothesis",
        "title": "El servidor soporta 100 usuarios concurrentes",
        "content": "Basado en pruebas de carga preliminares, el server podría soportar 100 usuarios.",
        "author": "damian",
        "confidence": 0.3,
        "importance": 0.8,
        "status": "hypothesis",
        "evidence": [{"quote": "prueba de carga preliminar", "weight": 0.5}],
    })
    assert resp.status_code == 201, resp.text
    return resp, client


def test_ingest_persists_and_echoes_rich_cognitive_fields(monkeypatch):
    db = InMemoryDatabase()
    vector_store = InMemoryVectorStore()
    resp, _ = _ingest_rich_hypothesis(monkeypatch, db, vector_store)
    body = resp.json()

    # 1. La respuesta de ingesta ecoa los valores ricos persistidos
    assert body["object_type"] == "hypothesis"
    assert body["confidence"] == 0.3
    assert body["importance"] == 0.8
    assert body["status"] == "hypothesis"


def test_rich_fields_survive_roundtrip_through_history_endpoint(monkeypatch):
    db = InMemoryDatabase()
    vector_store = InMemoryVectorStore()
    resp, client = _ingest_rich_hypothesis(monkeypatch, db, vector_store)
    node_id = resp.json()["node_id"]

    # 2. Recuperado por /history (lectura independiente, no el mismo objeto de respuesta)
    hist = client.get(f"/api/v1/memory/node/{node_id}/history")
    assert hist.status_code == 200, hist.text
    hist_body = hist.json()

    assert hist_body["object_type"] == "hypothesis"
    v1 = hist_body["versions"][0]
    assert v1["confidence"] == 0.3
    assert v1["importance"] == 0.8
    assert v1["status"] == "hypothesis"
    assert v1["evidence"] == [{"node_id": None, "url": None,
                               "quote": "prueba de carga preliminar", "weight": 0.5}]
    assert v1["salience"] == 0.5  # default, aún no recalculado (Fase 5)
    assert v1["tombstoned_at"] is None


def test_rich_fields_survive_roundtrip_through_search_endpoint(monkeypatch):
    db = InMemoryDatabase()
    vector_store = InMemoryVectorStore()
    _, client = _ingest_rich_hypothesis(monkeypatch, db, vector_store)

    # 3. Recuperado por /search (tercer camino de lectura independiente)
    search = client.post(
        "/api/v1/memory/search",
        params={"query": "El servidor soporta 100 usuarios concurrentes", "limit": 1},
    )
    assert search.status_code == 200, search.text
    results = search.json()["results"]
    assert len(results) == 1
    assert results[0]["object_type"] == "hypothesis"
    assert results[0]["confidence"] == 0.3
    assert results[0]["importance"] == 0.8
    assert results[0]["status"] == "hypothesis"
