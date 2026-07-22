"""
F3-T1: el router de aprobaciones resuelve los `pending_approval` que `CapabilityExecutor`
persiste (F1-T8) — aprobar despacha la capacidad diferida con sus inputs originales; rechazar
no despacha nada. En ambos casos el episodio del Thinking Graph queda con su resolución real
(F2-T2), no congelado en 'pending_approval' para siempre.
"""
import asyncio
from datetime import timedelta

import httpx
from fastapi.testclient import TestClient
from mindos_common.ids import new_id
from mindos_schemas.api.v1.agent_dto import PlanStep
from mindos_schemas.capabilities import Capability

from agents.src import main as agents_main
from agents.src.domain.executor.capability_executor import CapabilityExecutor
from agents.src.infrastructure.adapters.in_memory_approval_store import InMemoryApprovalStore
from agents.src.infrastructure.adapters.in_memory_capability_registry import (
    InMemoryCapabilityRegistry,
)
from memory.src import main as memory_main
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_thinking_graph import InMemoryThinkingGraph
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding


class _NoopBus:
    async def publish(self, *args, **kwargs):
        return "0-1"

    async def close(self):
        pass


def _wire_memory(monkeypatch):
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", InMemoryDatabase())
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    monkeypatch.setattr(memory_main, "in_memory_thinking_graph", InMemoryThinkingGraph())


def _seed_pending_approval(monkeypatch, memory_client, capability_name, provider_service):
    """Crea un episodio real en Memory y una aprobación pendiente real vía CapabilityExecutor
    (sin pasar por el grafo LangGraph completo, que ya se prueba en test_agent_graph.py)."""
    registry = InMemoryCapabilityRegistry()
    approval_store = InMemoryApprovalStore()
    monkeypatch.setattr(agents_main, "capability_registry", registry)
    monkeypatch.setattr(agents_main, "approval_store", approval_store)

    episode_id = new_id()
    ep_resp = memory_client.post("/api/v1/thinking/episodes", json={
        "episode_id": str(episode_id), "goal": "Acción sensible", "correlation_id": str(episode_id),
        "agent": "AgentsService",
    })
    assert ep_resp.status_code == 201, ep_resp.text

    async def _register_and_pause():
        cap = Capability(
            name=capability_name, description="Acción sensible", parameters_schema={},
            provider_service=provider_service, endpoint_path="/api/v1/x", requires_approval=True,
        )
        await registry.register([cap])
        executor = CapabilityExecutor(registry, approval_store=approval_store)
        step = PlanStep(
            step_id=1, task="paso sensible", capability_name=capability_name,
            expected_output="ok", status="pending",
        )
        return await executor.execute_step(step, {"confirm": "yes"}, episode_id=episode_id)

    result = asyncio.run(_register_and_pause())
    approval_id = result.output.split("approval_id=")[1].strip()
    return approval_id, episode_id


def test_get_approval_returns_pending_record(monkeypatch):
    _wire_memory(monkeypatch)
    memory_client = TestClient(memory_main.app)
    approval_id, episode_id = _seed_pending_approval(
        monkeypatch, memory_client, "delete_all_memory", "whatsapp"
    )

    agents_client = TestClient(agents_main.app)
    resp = agents_client.get(f"/api/v1/approvals/{approval_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["capability_name"] == "delete_all_memory"
    assert body["episode_id"] == str(episode_id)
    assert body["inputs"] == {"confirm": "yes"}


def test_resolving_approved_dispatches_the_deferred_capability_and_closes_episode(monkeypatch):
    _wire_memory(monkeypatch)
    memory_client = TestClient(memory_main.app)
    # provider_service "whatsapp" no resuelve a URL conocida en resolve_service_url -> el
    # Executor simula limpio (determinista, sin red), igual que en F1-T8.
    approval_id, episode_id = _seed_pending_approval(
        monkeypatch, memory_client, "notify_user", "whatsapp"
    )

    async def override_http_client():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=memory_main.app)) as client:
            yield client
    agents_main.app.dependency_overrides[agents_main.get_http_client] = override_http_client

    agents_client = TestClient(agents_main.app)
    try:
        with agents_client:
            resp = agents_client.post(f"/api/v1/approvals/{approval_id}/resolve", json={"approved": True})
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["executed"] is True
            assert body["approval"]["status"] == "approved"
            assert "Simulación" in body["approval"]["result_output"]

            # Resolver de nuevo debe fallar: ya no está pending.
            again = agents_client.post(f"/api/v1/approvals/{approval_id}/resolve", json={"approved": True})
            assert again.status_code == 409

        with memory_client:
            episode = memory_client.get(f"/api/v1/thinking/episodes/{episode_id}").json()
    finally:
        agents_main.app.dependency_overrides.clear()

    assert episode["status"] == "completed"
    assert "Simulación" in episode["final_output"]
    execute_steps = [s for s in episode["steps"] if s["kind"] == "execute" and s["approved"] is True]
    assert len(execute_steps) == 1


def test_resolving_rejected_does_not_dispatch(monkeypatch):
    _wire_memory(monkeypatch)
    memory_client = TestClient(memory_main.app)
    approval_id, episode_id = _seed_pending_approval(
        monkeypatch, memory_client, "delete_all_memory", "whatsapp"
    )

    async def override_http_client():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=memory_main.app)) as client:
            yield client
    agents_main.app.dependency_overrides[agents_main.get_http_client] = override_http_client

    agents_client = TestClient(agents_main.app)
    try:
        with agents_client:
            resp = agents_client.post(f"/api/v1/approvals/{approval_id}/resolve", json={"approved": False})
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["executed"] is False
            assert body["approval"]["status"] == "rejected"

        with memory_client:
            episode = memory_client.get(f"/api/v1/thinking/episodes/{episode_id}").json()
    finally:
        agents_main.app.dependency_overrides.clear()

    assert episode["status"] == "rejected"


def test_list_pending_returns_only_pending_most_recent_first(monkeypatch):
    monkeypatch.setattr(agents_main, "approval_store", InMemoryApprovalStore())
    store = agents_main.approval_store
    episode_id = new_id()

    first_id, second_id = new_id(), new_id()
    asyncio.run(store.create(
        approval_id=first_id, episode_id=episode_id, step_id=1,
        capability_name="notify_user", inputs={},
    ))
    asyncio.run(store.create(
        approval_id=second_id, episode_id=episode_id, step_id=2,
        capability_name="delete_all_memory", inputs={},
    ))
    # Fuerza un orden determinista: dos `datetime.now()` consecutivos pueden empatar según la
    # resolución del reloj, y un empate dejaría el orden sin definir (sort estable = orden de
    # inserción, no el "más reciente primero" que se quiere probar).
    store._approvals[first_id]["created_at"] -= timedelta(seconds=1)

    agents_client = TestClient(agents_main.app)
    resp = agents_client.get("/api/v1/approvals/")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [a["id"] for a in body["approvals"]] == [str(second_id), str(first_id)]
    assert all(a["status"] == "pending" for a in body["approvals"])

    # Resolverla la saca de la bandeja.
    resolve_resp = agents_client.post(f"/api/v1/approvals/{second_id}/resolve", json={"approved": False})
    assert resolve_resp.status_code == 200, resolve_resp.text
    after = agents_client.get("/api/v1/approvals/").json()
    assert [a["id"] for a in after["approvals"]] == [str(first_id)]


def test_resolving_unknown_approval_returns_404(monkeypatch):
    _wire_memory(monkeypatch)
    monkeypatch.setattr(agents_main, "approval_store", InMemoryApprovalStore())
    agents_client = TestClient(agents_main.app)
    resp = agents_client.post(f"/api/v1/approvals/{new_id()}/resolve", json={"approved": True})
    assert resp.status_code == 404
