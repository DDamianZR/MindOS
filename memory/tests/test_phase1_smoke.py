"""Cierre de Fase 1 — verificación integral end-to-end (plan/01-knowledge-core.md):
ingesta rica -> búsqueda con citas -> timetravel -> neighbors -> un agente que recupera
contexto real (GraphRAG) y ejecuta search_knowledge de verdad contra el Memory Service."""
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from mindos_schemas.api.v1.agent_dto import PlanStep
from mindos_schemas.capabilities import Capability

from agents.src.domain.executor.capability_executor import CapabilityExecutor
from agents.src.infrastructure.adapters.in_memory_capability_registry import (
    InMemoryCapabilityRegistry,
)
from memory.src import main as memory_main
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding


class _NoopBus:
    async def publish(self, *args, **kwargs):
        return "0-1"

    async def close(self):
        pass


def _patch_memory(monkeypatch):
    db = InMemoryDatabase()
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", db)
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    return db


def test_phase1_memory_smoke_ingest_context_timetravel_neighbors(monkeypatch):
    """Sin agentes: ingesta rica -> búsqueda con citas (/context) -> /timetravel -> /neighbors."""
    _patch_memory(monkeypatch)
    client = TestClient(memory_main.app)

    # 1. Ingesta rica: objeto cognitivo con confianza/importancia/estado/evidencia/origen
    ingest = client.post("/api/v1/memory/ingest", json={
        "object_type": "decision",
        "title": "Migrar a Traefik",
        "content": "Se decidió migrar el proxy reverso a Traefik por soporte nativo de TLS.",
        "author": "damian",
        "confidence": 0.9, "importance": 0.8, "status": "active",
        "evidence": [{"quote": "soporte nativo de TLS", "weight": 1.0}],
        "source": {"kind": "cli", "uri": "cli://decision-log/1"},
    })
    assert ingest.status_code == 201, ingest.text
    node_id = ingest.json()["node_id"]
    assert ingest.json()["confidence"] == 0.9

    ingest2 = client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "Config de Traefik",
        "content": "El puerto 443 quedó configurado.", "author": "damian", "importance": 0.6,
    })
    node2_id = ingest2.json()["node_id"]

    rel = client.post("/api/v1/memory/relation", json={
        "source_id": node_id, "target_id": node2_id, "relation_type": "LEADS_TO",
    })
    assert rel.status_code == 200, rel.text

    # 2. Búsqueda con citas (GraphRAG, F1-T7): el fragmento cita su node_id y su source
    ctx = client.post("/api/v1/memory/context", json={"query": "Traefik", "limit": 5, "depth": 1})
    assert ctx.status_code == 200, ctx.text
    bundle = ctx.json()
    cited_ids = {f["node_id"] for f in bundle["fragments"]}
    assert node_id in cited_ids
    decision_fragment = next(f for f in bundle["fragments"] if f["node_id"] == node_id)
    assert decision_fragment["source_id"] is not None

    # 3. Timetravel (F1-T3): "qué pensaba en esta fecha" (ahora, debe ver la v1 recién creada)
    now = datetime.now(timezone.utc).isoformat()
    tt = client.get("/api/v1/memory/timetravel", params={"node_id": node_id, "at": now})
    assert tt.status_code == 200, tt.text
    assert tt.json()["found"] is True
    assert tt.json()["version"]["title"] == "Migrar a Traefik"

    # 4. Neighbors (F1-T6): la relación LEADS_TO recién creada
    neighbors = client.get(f"/api/v1/memory/node/{node_id}/neighbors")
    assert neighbors.status_code == 200, neighbors.text
    assert any(
        n["target_id"] == node2_id and n["relation_type"] == "LEADS_TO"
        for n in neighbors.json()["neighbors"]
    )


@pytest.mark.asyncio
async def test_phase1_agent_executes_real_capability_against_memory_service(monkeypatch):
    """
    El Executor de Agents (F1-T8) despacha `search_knowledge` como una llamada HTTP REAL,
    servida por una instancia auténtica de la app FastAPI del Memory Service — vía
    `httpx.ASGITransport`, sin red real ni mocks de handler, para verificar el cableo completo
    de extremo a extremo sin mezclar clientes sync/async en el mismo event loop.
    """
    _patch_memory(monkeypatch)

    memory_asgi_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=memory_main.app), base_url="http://memory"
    )

    # Sembrar contenido real en la memoria para que la búsqueda tenga qué encontrar
    seed = await memory_asgi_client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "Puerto de Traefik",
        "content": "El puerto configurado para TLS es 443.", "author": "damian",
    })
    assert seed.status_code == 201

    registry = InMemoryCapabilityRegistry()
    cap = Capability(
        name="search_knowledge", description="Busca en memoria",
        parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        provider_service="memory", endpoint_path="/api/v1/memory/search",
    )
    await registry.register([cap])

    executor = CapabilityExecutor(
        registry,
        service_url_resolver=lambda svc: "http://memory" if svc == "memory" else None,
        http_client=memory_asgi_client,
    )
    step = PlanStep(
        step_id=1, task="Buscar puerto de Traefik", capability_name="search_knowledge",
        expected_output="El puerto encontrado", status="pending",
    )

    result = await executor.execute_step(step, {"query": "puerto configurado para TLS"})

    assert result.status == "completed"
    assert "443" in result.output, f"se esperaba el resultado real de la búsqueda; output={result.output!r}"
    await executor.close()
