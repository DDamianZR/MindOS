"""GET /api/v1/memory/stats con el backend en memoria, valor por valor."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from memory.src import main as memory_main
from memory.src.application.services.stats_service import StatsService
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding
from memory.src.infrastructure.adapters.mock_llm import MockLlm

_THINKING = {"decision", "insight", "learning", "hypothesis"}


class _NoopBus:
    async def publish(self, *args, **kwargs):
        return "0-1"

    async def close(self):
        pass


class _SnapshotDatabase:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    async def get_stats_snapshot(self):
        return self.snapshot


def _client(monkeypatch):
    db = InMemoryDatabase()
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "llm_provider", MockLlm())
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", db)
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    return TestClient(memory_main.app), db


def _stamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def test_stats_of_empty_memory_are_zero_with_thirty_days(monkeypatch):
    client, _db = _client(monkeypatch)
    resp = client.get("/api/v1/memory/stats")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["nodes"] == 0
    assert body["archived_nodes"] == 0
    assert body["versions"] == 0
    assert body["relations"] == 0
    assert body["sources"] == 0
    assert body["contradictions"] == 0
    assert body["by_type"] == []
    assert body["by_source"] == []
    assert body["by_relation"] == []
    assert body["recent_thinking"] == []

    today = datetime.now(timezone.utc).date()
    activity = body["activity"]
    assert [day["date"] for day in activity] == [
        (today - timedelta(days=offset)).isoformat() for offset in range(29, -1, -1)
    ]
    assert all(day["created"] == 0 and day["updated"] == 0 for day in activity)


def test_stats_reflect_ingest_version_archive_relations_and_source(monkeypatch):
    client, db = _client(monkeypatch)
    tracked: list[dict] = []

    def ingest(object_type, title, content, *, node_id=None, source=None):
        payload = {
            "object_type": object_type,
            "title": title,
            "content": content,
            "author": "damian",
            "on_duplicate": "force_new",
        }
        if node_id is not None:
            payload["node_id"] = node_id
        if source is not None:
            payload["source"] = source
        resp = client.post("/api/v1/memory/ingest", json=payload)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        tracked[:] = [item for item in tracked if item["node_id"] != body["node_id"]]
        if body["object_type"] in _THINKING:
            tracked.append({
                "node_id": body["node_id"],
                "version": body["version"],
                "title": body["title"],
                "object_type": body["object_type"],
                "created_at": body["created_at"],
            })
        return body

    def relate(source_id, target_id, relation_type):
        resp = client.post("/api/v1/memory/relation", json={
            "source_id": source_id, "target_id": target_id, "relation_type": relation_type,
        })
        assert resp.status_code == 200, resp.text

    note = ingest(
        "note", "Nota de arquitectura", "El servicio de memoria guarda el grafo.",
        source={"kind": "pdf", "uri": "file:///docs/arquitectura.pdf"},
    )
    decision = ingest("decision", "Elegir Postgres", "Guardar el grafo en Postgres.")
    insight = ingest("insight", "El cache ayuda", "Cachear lecturas bajó la latencia.")
    learning = ingest("learning", "Medir antes de cambiar", "Sin medida no sé si mejoró.")
    hypothesis = ingest("hypothesis", "Mas replicas, menos latencia", "Si subo replicas, baja la latencia.")
    active_insight = ingest("insight", "Los indices importan", "Un indice en node_id abarata el historial.")
    idea = ingest(
        "idea", "Separar lecturas", "Un replica de lectura para las consultas.",
        source={"kind": "whatsapp", "uri": "whatsapp://msg/arquitectura-1"},
    )
    ingest(
        "decision", "Elegir Postgres y pgvector", "Postgres con pgvector para el grafo y la busqueda.",
        node_id=decision["node_id"],
    )

    archived = client.post(f"/api/v1/memory/node/{insight['node_id']}/archive")
    assert archived.status_code == 200, archived.text
    tracked[:] = [item for item in tracked if item["node_id"] != insight["node_id"]]

    extras = [
        ingest("decision", f"Decision de seguimiento {index}", f"Seguimiento {index} del plan de capacidad.")
        for index in range(5)
    ]

    relate(learning["node_id"], decision["node_id"], "EVIDENCES")
    relate(hypothesis["node_id"], active_insight["node_id"], "CONTRADICTS")
    relate(idea["node_id"], note["node_id"], "SUPPORTS")
    asyncio.run(db.delete_relation(UUID(idea["node_id"]), UUID(note["node_id"]), "SUPPORTS"))

    resp = client.get("/api/v1/memory/stats")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["nodes"] == 11
    assert body["archived_nodes"] == 1
    assert body["versions"] == 13
    assert body["relations"] == 2
    assert body["sources"] == 2
    assert body["contradictions"] == 1
    assert body["by_type"] == [
        {"key": "decision", "count": 6},
        {"key": "hypothesis", "count": 1},
        {"key": "idea", "count": 1},
        {"key": "insight", "count": 1},
        {"key": "learning", "count": 1},
        {"key": "note", "count": 1},
    ]
    assert body["by_source"] == [
        {"key": "pdf", "count": 1},
        {"key": "whatsapp", "count": 1},
    ]
    assert body["by_relation"] == [
        {"key": "CONTRADICTS", "count": 1},
        {"key": "EVIDENCES", "count": 1},
    ]

    today = datetime.now(timezone.utc).date()
    activity = body["activity"]
    assert [day["date"] for day in activity] == [
        (today - timedelta(days=offset)).isoformat() for offset in range(29, -1, -1)
    ]
    assert all(day["created"] == 0 and day["updated"] == 0 for day in activity[:-1])
    assert activity[-1]["created"] == 12
    assert activity[-1]["updated"] == 1

    assert len(tracked) == 9
    tracked.sort(key=lambda item: (_stamp(item["created_at"]), item["node_id"]), reverse=True)
    expected = tracked[:8]
    recent = body["recent_thinking"]
    assert [(item["node_id"], item["version"], item["title"], item["object_type"]) for item in recent] == [
        (item["node_id"], item["version"], item["title"], item["object_type"]) for item in expected
    ]
    recent_ids = {item["node_id"] for item in recent}
    assert insight["node_id"] not in recent_ids
    assert learning["node_id"] not in recent_ids
    assert note["node_id"] not in recent_ids
    assert idea["node_id"] not in recent_ids
    assert decision["node_id"] in recent_ids
    assert next(item["version"] for item in recent if item["node_id"] == decision["node_id"]) == 2
    assert active_insight["node_id"] in recent_ids
    assert hypothesis["node_id"] in recent_ids
    assert all(item["node_id"] in recent_ids for item in extras)


async def test_service_orders_counts_fills_gaps_and_caps_thinking():
    today = datetime.now(timezone.utc).date()
    mid = today - timedelta(days=10)
    outside = today - timedelta(days=40)
    base = datetime.now(timezone.utc)
    note_id = UUID(int=1)
    outcome_id = UUID(int=2)
    thinking_ids = [UUID(int=index) for index in range(3, 12)]
    kinds = [
        "decision", "insight", "learning", "hypothesis", "decision",
        "insight", "learning", "hypothesis", "decision",
    ]
    recent = [
        {
            "node_id": note_id, "title": "Nota reciente", "object_type": "note",
            "version": 1, "created_at": base,
        },
        {
            "node_id": outcome_id, "title": "Resultado", "object_type": "outcome",
            "version": 1, "created_at": base - timedelta(minutes=1),
        },
    ]
    for index, (node_id, kind) in enumerate(zip(thinking_ids, kinds, strict=True)):
        recent.append({
            "node_id": node_id,
            "title": f"{kind}-{index}",
            "object_type": kind,
            "version": 4 if index == 0 else 1,
            "created_at": base - timedelta(minutes=index + 2),
        })

    stats = await StatsService(_SnapshotDatabase({
        "nodes": 11,
        "archived_nodes": 1,
        "versions": 13,
        "relations": 2,
        "sources": 2,
        "contradictions": 1,
        "by_type": [
            {"key": "note", "count": 1},
            {"key": "decision", "count": 4},
            {"key": "idea", "count": 4},
        ],
        "by_source": [
            {"key": "web", "count": 5},
            {"key": "cli", "count": 5},
            {"key": "pdf", "count": 1},
        ],
        "by_relation": [
            {"key": "EVIDENCES", "count": 3},
            {"key": "SUPPORTS", "count": 1},
            {"key": "CONTRADICTS", "count": 3},
        ],
        "activity": [
            {"date": outside, "created": 9, "updated": 9},
            {"date": mid, "created": 2, "updated": 4},
            {"date": today, "created": 1, "updated": 0},
        ],
        "recent_thinking": recent,
    })).get_stats()

    assert stats.nodes == 11
    assert stats.archived_nodes == 1
    assert stats.versions == 13
    assert stats.relations == 2
    assert stats.sources == 2
    assert stats.contradictions == 1
    assert [(item.key, item.count) for item in stats.by_type] == [
        ("decision", 4), ("idea", 4), ("note", 1),
    ]
    assert [(item.key, item.count) for item in stats.by_source] == [
        ("cli", 5), ("web", 5), ("pdf", 1),
    ]
    assert [(item.key, item.count) for item in stats.by_relation] == [
        ("CONTRADICTS", 3), ("EVIDENCES", 3), ("SUPPORTS", 1),
    ]
    assert len(stats.activity) == 30
    assert stats.activity[0].date == today - timedelta(days=29)
    assert stats.activity[-1].date == today
    assert stats.activity[-1].created == 1
    assert stats.activity[-1].updated == 0
    mid_day = next(day for day in stats.activity if day.date == mid)
    assert mid_day.created == 2
    assert mid_day.updated == 4
    gap = next(day for day in stats.activity if day.date == mid + timedelta(days=1))
    assert gap.created == 0
    assert gap.updated == 0
    assert all(day.date != outside for day in stats.activity)
    assert [item.node_id for item in stats.recent_thinking] == thinking_ids[:8]
    assert stats.recent_thinking[0].version == 4
    assert stats.recent_thinking[0].object_type == "decision"
    assert note_id not in {item.node_id for item in stats.recent_thinking}
    assert outcome_id not in {item.node_id for item in stats.recent_thinking}
    assert thinking_ids[8] not in {item.node_id for item in stats.recent_thinking}
    assert stats.generated_at.tzinfo is not None
