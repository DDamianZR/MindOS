"""F0-T6: la ingesta debe ser event-driven: escribir en el event_log durable y publicar en el bus."""
from fastapi.testclient import TestClient

from memory.src import main as memory_main
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding


class FakeBus:
    """Bus falso que registra las publicaciones en memoria (sin Redis)."""
    def __init__(self):
        self.published = []

    async def publish(self, stream_name, event_type, event_data, correlation_id):
        self.published.append({
            "stream": stream_name,
            "type": event_type,
            "data": event_data,
            "correlation_id": correlation_id,
        })
        return "0-1"

    async def close(self):
        pass


def test_ingest_emits_event_and_writes_event_log(monkeypatch):
    # Embeddings deterministas sin depender de Ollama
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    fake_bus = FakeBus()
    monkeypatch.setattr(memory_main, "event_bus", fake_bus)

    events_before = len(memory_main.in_memory_db._events)

    client = TestClient(memory_main.app)
    resp = client.post("/api/v1/memory/ingest", json={
        "object_type": "note",
        "title": "Traefik",
        "content": "El puerto 443 quedó configurado para TLS.",
        "author": "damian",
        "metadata": {},
    })

    assert resp.status_code == 201, resp.text

    # 1. El event_log durable creció en 1 con el tipo correcto
    assert len(memory_main.in_memory_db._events) == events_before + 1
    last_event = memory_main.in_memory_db._events[-1]
    assert last_event["event_type"] == "com.mindos.memory.knowledge.created"

    # 2. Se publicó exactamente un evento en el bus, con correlation_id y en el stream correcto
    assert len(fake_bus.published) == 1
    pub = fake_bus.published[0]
    assert pub["type"] == "com.mindos.memory.knowledge.created"
    assert pub["stream"] == "mindos.memory"
    assert pub["correlation_id"] is not None


def test_ingest_propagates_incoming_correlation_id(monkeypatch):
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    fake_bus = FakeBus()
    monkeypatch.setattr(memory_main, "event_bus", fake_bus)

    client = TestClient(memory_main.app)
    corr = "019f8364-cb61-71d7-91d3-49f1a2c0f3a3"
    resp = client.post(
        "/api/v1/memory/ingest",
        headers={"X-Correlation-Id": corr},
        json={"object_type": "note", "title": "t", "content": "c", "author": "a", "metadata": {}},
    )
    assert resp.status_code == 201
    assert str(fake_bus.published[-1]["correlation_id"]) == corr
