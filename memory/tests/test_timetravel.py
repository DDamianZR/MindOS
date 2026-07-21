"""F1-T3: consulta temporal 'as-of' — reconstruir el estado del conocimiento en cualquier fecha.
Nodo con v1 (enero) y v2 (marzo): as-of febrero devuelve v1; as-of hoy devuelve v2. Las
relaciones deben respetar su intervalo de validez bitemporal (valid_from/valid_to)."""
import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from mindos_common.ids import new_id

from memory.src import main as memory_main
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding

JAN = datetime(2026, 1, 15, tzinfo=timezone.utc)
FEB = datetime(2026, 2, 15, tzinfo=timezone.utc)
MAR = datetime(2026, 3, 15, tzinfo=timezone.utc)
NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)


async def _seed_node_with_two_versions(db: InMemoryDatabase, node_id):
    await db.save_node(node_id, "note")

    v1_id = new_id()
    await db.save_node_version(
        node_id=node_id, version_id=v1_id, version=1,
        title="v1 - enero", content="pensaba que el bug era de red", author="damian", metadata={},
    )
    # Forzar el created_at real de v1 a enero (el default es "ahora"; lo pisamos para el test).
    db._versions[node_id][-1]["created_at"] = JAN

    v2_id = new_id()
    await db.save_node_version(
        node_id=node_id, version_id=v2_id, version=2,
        title="v2 - marzo", content="en realidad era un race condition", author="damian", metadata={},
        parent_version_id=v1_id,
    )
    db._versions[node_id][-1]["created_at"] = MAR

    return v1_id, v2_id


async def test_asof_february_returns_v1_and_asof_now_returns_v2():
    db = InMemoryDatabase()
    node_id = new_id()
    await _seed_node_with_two_versions(db, node_id)

    asof_feb = await db.get_node_version_asof(node_id, FEB)
    assert asof_feb["version"] == 1
    assert asof_feb["title"] == "v1 - enero"

    asof_now = await db.get_node_version_asof(node_id, NOW)
    assert asof_now["version"] == 2
    assert asof_now["title"] == "v2 - marzo"

    # Antes de que el nodo existiera: no hay snapshot.
    before_creation = datetime(2025, 12, 1, tzinfo=timezone.utc)
    assert await db.get_node_version_asof(node_id, before_creation) is None


async def test_relations_respect_bitemporal_validity_window():
    db = InMemoryDatabase()
    a, b, c = new_id(), new_id(), new_id()
    for n in (a, b, c):
        await db.save_node(n, "note")

    # Relación A->B activa desde enero, cerrada (superseded) en marzo.
    db._relations.append({
        "source_id": a, "target_id": b, "relation_type": "RELATED_TO",
        "valid_from": JAN, "valid_to": MAR, "metadata": {},
    })
    # Relación A->C activa desde marzo, sigue vigente hoy.
    db._relations.append({
        "source_id": a, "target_id": c, "relation_type": "RELATED_TO",
        "valid_from": MAR, "valid_to": None, "metadata": {},
    })

    # En febrero: solo A->B estaba activa (A->C aún no existía).
    rels_feb = await db.query_relations_asof(a, FEB, max_depth=1)
    targets_feb = {r["target_id"] for r in rels_feb}
    assert targets_feb == {b}

    # Hoy: A->B ya cerró (valid_to=marzo < hoy), A->C sigue activa.
    rels_now = await db.query_relations_asof(a, NOW, max_depth=1)
    targets_now = {r["target_id"] for r in rels_now}
    assert targets_now == {c}


class _NoopBus:
    async def publish(self, *args, **kwargs):
        return "0-1"

    async def close(self):
        pass


def test_timetravel_endpoint_returns_correct_version_and_missing_before_creation(monkeypatch):
    db = InMemoryDatabase()
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", db)
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())

    node_id = new_id()
    asyncio.run(_seed_node_with_two_versions(db, node_id))

    client = TestClient(memory_main.app)

    resp_feb = client.get("/api/v1/memory/timetravel", params={"node_id": str(node_id), "at": FEB.isoformat()})
    assert resp_feb.status_code == 200, resp_feb.text
    body_feb = resp_feb.json()
    assert body_feb["found"] is True
    assert body_feb["version"]["version"] == 1

    resp_before = client.get(
        "/api/v1/memory/timetravel",
        params={"node_id": str(node_id), "at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()},
    )
    assert resp_before.json()["found"] is False
