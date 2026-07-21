"""F1-T7: el endpoint POST /api/v1/memory/context expone el Context Builder v2 (GraphRAG)
sobre HTTP, con fragmentos citables (node_id + source) ordenados por el score combinado."""
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


def test_context_endpoint_returns_fragments_with_node_id_and_source(monkeypatch):
    client, _ = _fresh_client(monkeypatch)

    ingest = client.post("/api/v1/memory/ingest", json={
        "object_type": "document", "title": "Manual de Traefik",
        "content": "El puerto 443 está configurado para TLS.", "author": "damian",
        "importance": 0.9,
        "source": {"kind": "pdf", "uri": "file:///traefik.pdf"},
    })
    node_id = ingest.json()["node_id"]

    resp = client.post("/api/v1/memory/context", json={
        "query": "El puerto 443 está configurado para TLS.", "limit": 3, "depth": 1,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["query"] == "El puerto 443 está configurado para TLS."
    assert len(body["fragments"]) == 1
    fragment = body["fragments"][0]
    assert fragment["node_id"] == node_id
    assert fragment["citation_label"] == "n1"
    assert fragment["source_id"] is not None  # provenance trazable
    assert fragment["importance"] == 0.9
