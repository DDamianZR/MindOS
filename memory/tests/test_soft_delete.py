"""F1-T4: soft-delete / tombstone global. Archivar un nodo lo saca de la búsqueda y de las
lecturas por defecto, pero `include_archived=true` lo recupera; nunca se borra físicamente."""
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


def test_archive_hides_node_from_search_and_history_reads_but_restore_recovers_it(monkeypatch):
    client, db = _fresh_client(monkeypatch)

    ingest = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "Nota archivable",
        "content": "Contenido único e irrepetible para búsqueda exacta.", "author": "damian",
    })
    node_id = ingest.json()["node_id"]

    def search_finds_it():
        resp = client.post("/api/v1/memory/search",
                            params={"query": "Contenido único e irrepetible para búsqueda exacta.", "limit": 5})
        ids = [r["node_id"] for r in resp.json()["results"]]
        return node_id in ids

    # 1. Antes de archivar: aparece en la búsqueda.
    assert search_finds_it()

    # 2. Archivar (soft-delete) — nunca borra físicamente la fila.
    archive = client.post(f"/api/v1/memory/node/{node_id}/archive")
    assert archive.status_code == 200, archive.text
    assert archive.json() == {"node_id": node_id, "archived": True}
    assert node_id in {str(k) for k in db._versions}, "el nodo sigue existiendo físicamente"

    # 3. Tras archivar: desaparece de la búsqueda por defecto...
    assert not search_finds_it()
    # ...pero get_latest_node_version por defecto también lo oculta (no cae a versión vieja).
    hist_default = client.get(f"/api/v1/memory/node/{node_id}/history")
    assert hist_default.status_code == 200
    assert hist_default.json()["versions"][-1]["tombstoned_at"] is not None

    # 4. Con include_archived=true, la búsqueda SÍ lo recupera.
    resp_incl = client.post(
        "/api/v1/memory/search",
        params={"query": "Contenido único e irrepetible para búsqueda exacta.",
                "limit": 5, "include_archived": True},
    )
    ids_incl = [r["node_id"] for r in resp_incl.json()["results"]]
    assert node_id in ids_incl

    # 5. Restaurar: vuelve a aparecer en la búsqueda por defecto.
    restore = client.post(f"/api/v1/memory/node/{node_id}/restore")
    assert restore.status_code == 200
    assert restore.json() == {"node_id": node_id, "archived": False}
    assert search_finds_it()


def test_archiving_nonexistent_node_returns_404(monkeypatch):
    client, _ = _fresh_client(monkeypatch)
    resp = client.post("/api/v1/memory/node/019f8364-cb61-71d7-91d3-49f1a2c0f3a3/archive")
    assert resp.status_code == 404


def test_no_api_route_hard_deletes_knowledge(monkeypatch):
    """Defensa explícita del principio 'nada se pierde': ninguna ruta debe ser un borrado físico."""
    client, _ = _fresh_client(monkeypatch)
    routes = [r.path for r in memory_main.app.routes if hasattr(r, "path")]
    assert not any("delete" in p.lower() for p in routes), (
        f"No debe existir ninguna ruta de borrado físico; encontradas: {routes}"
    )
