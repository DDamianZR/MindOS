"""F1-T2: una versión ingerida con `source` debe devolver esa fuente en /provenance,
y reutilizar la misma fuente (kind, uri) en vez de duplicarla si se reingiere."""
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


def _client_with_fresh_state(monkeypatch):
    db = InMemoryDatabase()
    vector_store = InMemoryVectorStore()
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", db)
    monkeypatch.setattr(memory_main, "in_memory_vector_store", vector_store)
    return TestClient(memory_main.app), db


def test_ingest_with_source_appears_in_provenance(monkeypatch):
    client, _ = _client_with_fresh_state(monkeypatch)

    resp = client.post("/api/v1/memory/ingest", json={
        "object_type": "document",
        "title": "Manual de Traefik",
        "content": "El puerto por defecto de Traefik es 443 para TLS.",
        "author": "damian",
        "source": {"kind": "pdf", "uri": "file:///docs/traefik-manual.pdf", "raw_ref": "page-12"},
    })
    assert resp.status_code == 201, resp.text
    node_id = resp.json()["node_id"]

    prov = client.get(f"/api/v1/memory/node/{node_id}/provenance")
    assert prov.status_code == 200, prov.text
    chain = prov.json()["chain"]

    assert len(chain) == 1
    assert chain[0]["version"] == 1
    source = chain[0]["source"]
    assert source is not None
    assert source["kind"] == "pdf"
    assert source["uri"] == "file:///docs/traefik-manual.pdf"
    assert source["raw_ref"] == "page-12"


def test_reingesting_same_uri_reuses_source_instead_of_duplicating(monkeypatch):
    client, db = _client_with_fresh_state(monkeypatch)
    uri = "whatsapp://msg/12345"

    first = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "n1", "content": "primer mensaje", "author": "damian",
        "source": {"kind": "whatsapp", "uri": uri},
    })
    second = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "n2", "content": "segundo mensaje", "author": "damian",
        "source": {"kind": "whatsapp", "uri": uri},
    })
    assert first.status_code == 201 and second.status_code == 201

    # Solo debe existir UNA fuente en el almacén, reutilizada por ambos nodos.
    assert len(db._sources) == 1


def test_ingest_without_source_has_empty_source_in_provenance(monkeypatch):
    client, _ = _client_with_fresh_state(monkeypatch)

    resp = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "sin origen", "content": "capturado directo", "author": "damian",
    })
    node_id = resp.json()["node_id"]

    prov = client.get(f"/api/v1/memory/node/{node_id}/provenance")
    assert prov.json()["chain"][0]["source"] is None
