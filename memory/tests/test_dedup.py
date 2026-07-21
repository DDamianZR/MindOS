"""F1-T5: dedup semántico en ingest. Por defecto (`on_duplicate=link`), ingerir dos textos
casi-idénticos produce un enlace DUPLICATE_OF en vez de dos nodos aislados.

`MockEmbedding` es un hash determinista del texto crudo, NO un embedding semántico: solo
detecta duplicados **exactos** (mismo texto), no *casi*-duplicados parafraseados. Por eso los
tests de mecánica/wiring usan contenido idéntico con el mock, y la detección de duplicados
*semánticamente similares pero no idénticos* se valida aparte con Ollama real (marcado
`integration`, se salta si Ollama no está disponible)."""
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from memory.src import main as memory_main
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding
from memory.src.infrastructure.adapters.ollama_embedding import OllamaEmbedding


class _NoopBus:
    async def publish(self, *args, **kwargs):
        return "0-1"

    async def close(self):
        pass


IDENTICAL_CONTENT = "El servidor de producción corre Ubuntu con Traefik en el puerto 443."


def _fresh_client(monkeypatch, embedding=None):
    db = InMemoryDatabase()
    monkeypatch.setattr(memory_main, "embedding_provider", embedding or MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", db)
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    return TestClient(memory_main.app), db


def test_default_link_mode_creates_duplicate_of_relation(monkeypatch):
    client, db = _fresh_client(monkeypatch)

    first = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "Config original", "content": IDENTICAL_CONTENT, "author": "damian",
    })
    assert first.status_code == 201
    original_id = first.json()["node_id"]
    assert first.json()["duplicate_of"] is None  # el primero no puede ser duplicado de nada

    second = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "Config repetida", "content": IDENTICAL_CONTENT, "author": "damian",
    })
    assert second.status_code == 201
    second_body = second.json()
    new_id = second_body["node_id"]

    # Se creó un NODO NUEVO (no una versión del original)...
    assert new_id != original_id
    # ...pero reportado y enlazado como duplicado del original.
    assert second_body["duplicate_of"] == original_id
    assert second_body["duplicate_score"] >= 0.92

    relations = [r for r in db._relations if r["source_id"] == UUID(new_id)]
    assert len(relations) == 1
    assert relations[0]["relation_type"] == "DUPLICATE_OF"
    assert relations[0]["target_id"] == UUID(original_id)


def test_force_new_ignores_duplicate_and_creates_isolated_node(monkeypatch):
    client, db = _fresh_client(monkeypatch)

    first = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "n1", "content": IDENTICAL_CONTENT, "author": "damian",
    })
    original_id = first.json()["node_id"]

    second = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "n2", "content": IDENTICAL_CONTENT, "author": "damian",
        "on_duplicate": "force_new",
    })
    body = second.json()
    assert body["duplicate_of"] is None
    assert not any(r["source_id"] == UUID(body["node_id"]) for r in db._relations)
    assert body["node_id"] != original_id


def test_new_version_mode_versions_existing_node_instead_of_creating_new_one(monkeypatch):
    client, db = _fresh_client(monkeypatch)

    first = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "n1", "content": IDENTICAL_CONTENT, "author": "damian",
    })
    original_id = first.json()["node_id"]

    second = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "n1 corregida", "content": IDENTICAL_CONTENT, "author": "damian",
        "on_duplicate": "new_version",
    })
    body = second.json()

    # Mismo node_id: se versionó el existente, no se creó uno nuevo.
    assert body["node_id"] == original_id
    assert body["version"] == 2
    assert body["duplicate_of"] == original_id
    # No debe crear relación DUPLICATE_OF: es el mismo nodo, no dos nodos enlazados.
    assert not any(r["relation_type"] == "DUPLICATE_OF" for r in db._relations)


def test_dedup_skipped_when_node_id_explicitly_provided(monkeypatch):
    client, db = _fresh_client(monkeypatch)

    first = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "n1", "content": IDENTICAL_CONTENT, "author": "damian",
    })
    original_id = first.json()["node_id"]

    # Ingesta explícita de otro nodo (auto-generado) que YA especifica su propio node_id.
    other_id = "019f8364-cb61-71d7-91d3-49f1a2c0f3a3"
    second = client.post("/api/v1/memory/ingest", json={
        "node_id": other_id,
        "object_type": "note", "title": "n2", "content": IDENTICAL_CONTENT, "author": "damian",
    })
    body = second.json()
    assert body["node_id"] == other_id
    assert body["duplicate_of"] is None  # dedup no aplica: el caller ya sabe qué nodo es
    assert not any(r["source_id"] == UUID(other_id) for r in db._relations)
    assert original_id != other_id


def _ollama_available() -> bool:
    try:
        httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _ollama_available(), reason="Ollama no está corriendo en localhost:11434")
def test_near_duplicate_with_minor_wording_difference_detected_with_real_embeddings(monkeypatch):
    """
    A diferencia de los tests anteriores (MockEmbedding, duplicado EXACTO byte a byte), este
    valida detección semántica real con Ollama: dos redacciones CASI idénticas (difieren en
    puntuación/capitalización, no en contenido) deben superar el umbral de dedup.

    Nota calibrada empíricamente (2026-07-21, nomic-embed-text): variaciones menores (typo,
    mayúsculas, puntuación) puntúan ~0.99 de similitud coseno; una PARÁFRASIS con vocabulario
    distinto del mismo hecho puntúa ~0.81 — por debajo del umbral de dedup (0.92). Esto es
    esperado y correcto: 0.92 está calibrado para capturar duplicados casi-verbatim (mismo
    mensaje reenviado, capturas repetidas), no para fusionar ideas distintas sobre el mismo tema.
    """
    real_embedding = OllamaEmbedding("http://localhost:11434", "nomic-embed-text")
    client, _ = _fresh_client(monkeypatch, embedding=real_embedding)

    # El context manager mantiene un único event loop para ambas peticiones: el httpx.AsyncClient
    # interno de OllamaEmbedding queda atado a esa conexión y no puede reutilizarse entre loops.
    with client:
        first = client.post("/api/v1/memory/ingest", json={
            "object_type": "note", "title": "Traefik",
            "content": "El puerto por defecto de Traefik para TLS es el 443.",
            "author": "damian",
        })
        original_id = first.json()["node_id"]

        second = client.post("/api/v1/memory/ingest", json={
            "object_type": "note", "title": "Traefik (recapturado)",
            "content": "el puerto por defecto de traefik para tls es el 443",
            "author": "damian",
        })
        body = second.json()

    assert body["duplicate_of"] == original_id, (
        f"Se esperaba detectar casi-duplicado semántico; score={body.get('duplicate_score')}"
    )
