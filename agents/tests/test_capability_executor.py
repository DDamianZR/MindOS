"""F1-T8: el Executor despacha capacidades reales vía HTTP al servicio proveedor, y respeta
el gate de aprobación (requires_approval) sin ejecutar nada en ese caso."""
from uuid import UUID

import httpx
import pytest
from mindos_common.ids import new_id
from mindos_schemas.api.v1.agent_dto import PlanStep
from mindos_schemas.capabilities import Capability

from agents.src.domain.executor.capability_executor import CapabilityExecutor
from agents.src.infrastructure.adapters.in_memory_capability_registry import (
    InMemoryCapabilityRegistry,
)


def _step(capability_name="search_knowledge"):
    return PlanStep(
        step_id=1, task="Buscar en memoria", capability_name=capability_name,
        expected_output="Resultados encontrados", status="pending",
    )


@pytest.mark.asyncio
async def test_executor_dispatches_real_http_call_to_resolved_service():
    """DoD F1-T8: un paso que usa search_knowledge hace una llamada HTTP real al servicio
    resuelto y devuelve el resultado real (no una simulación)."""
    calls = []

    def fake_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.path == "/api/v1/memory/search"
        assert dict(request.url.params) == {"query": "puerto de traefik"}
        return httpx.Response(200, json={"query": "puerto de traefik", "results": [
            {"node_id": "018b10f8-e1a5-7b18-b2a6-382a93414900", "version": 1,
             "title": "Traefik", "content": "El puerto es 443", "score": 0.9, "metadata": {}}
        ]})

    registry = InMemoryCapabilityRegistry()
    cap = Capability(
        name="search_knowledge", description="Busca en memoria",
        parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        provider_service="memory", endpoint_path="/api/v1/memory/search",
    )
    await registry.register([cap])

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(fake_handler))
    executor = CapabilityExecutor(
        registry, service_url_resolver=lambda svc: "http://memory:8001" if svc == "memory" else None,
        http_client=http_client,
    )

    result = await executor.execute_step(_step(), {"query": "puerto de traefik"}, episode_id=new_id())

    assert len(calls) == 1, "debe haberse hecho exactamente una llamada HTTP real"
    assert result.status == "completed"
    assert "Traefik" in result.output
    assert "443" in result.output
    await executor.close()


@pytest.mark.asyncio
async def test_capability_requiring_approval_pauses_without_dispatching():
    """DoD F1-T8: una capacidad con requires_approval=true queda en pending_approval,
    sin llegar a despachar ninguna llamada HTTP."""
    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No debería despacharse ninguna llamada HTTP para una capacidad sensible")

    registry = InMemoryCapabilityRegistry()
    sensitive_cap = Capability(
        name="delete_all_memory", description="Acción destructiva",
        parameters_schema={"type": "object", "properties": {}},
        provider_service="memory", endpoint_path="/api/v1/memory/wipe",
        requires_approval=True,
    )
    await registry.register([sensitive_cap])

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(failing_handler))
    executor = CapabilityExecutor(
        registry, service_url_resolver=lambda _svc: "http://memory:8001", http_client=http_client,
    )

    episode_id = new_id()
    result = await executor.execute_step(
        _step(capability_name="delete_all_memory"), {}, episode_id=episode_id,
        reply_to={"provider": "whatsapp", "sender_id": "5215512345678"},
    )

    assert result.status == "pending_approval"
    assert "aprobación" in result.output.lower()
    await executor.close()


@pytest.mark.asyncio
async def test_capability_requiring_approval_persists_a_resolvable_approval_request():
    """F3-T1/F3-T7: pausar una capacidad sensible debe dejar un ApprovalRequest durable con
    todo lo necesario para resolverla más tarde (capacidad, inputs, episodio, canal de origen)."""
    registry = InMemoryCapabilityRegistry()
    sensitive_cap = Capability(
        name="delete_all_memory", description="Acción destructiva", parameters_schema={},
        provider_service="memory", endpoint_path="/api/v1/memory/wipe", requires_approval=True,
    )
    await registry.register([sensitive_cap])

    executor = CapabilityExecutor(registry)
    episode_id = new_id()
    result = await executor.execute_step(
        _step(capability_name="delete_all_memory"), {"confirm": "yes"}, episode_id=episode_id,
        reply_to={"provider": "whatsapp", "sender_id": "5215512345678"},
    )

    approval_id_str = result.output.split("approval_id=")[1].strip()
    stored = await executor.approval_store.get(UUID(approval_id_str))
    assert stored is not None
    assert stored["status"] == "pending"
    assert stored["episode_id"] == episode_id
    assert stored["capability_name"] == "delete_all_memory"
    assert stored["inputs"] == {"confirm": "yes"}
    assert stored["reply_to"] == {"provider": "whatsapp", "sender_id": "5215512345678"}
    await executor.close()


@pytest.mark.asyncio
async def test_mock_handler_takes_precedence_over_http_dispatch():
    """Los mock handlers (solo tests) se siguen respetando: no deben intentar HTTP real."""
    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No debería usarse HTTP si hay un mock handler registrado")

    registry = InMemoryCapabilityRegistry()
    cap = Capability(
        name="search_knowledge", description="Busca en memoria", parameters_schema={},
        provider_service="memory", endpoint_path="/api/v1/memory/search",
    )
    await registry.register([cap])

    async def mock_handler(inputs):
        return "resultado mockeado"

    executor = CapabilityExecutor(
        registry, service_url_resolver=lambda _svc: "http://memory:8001",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(failing_handler)),
    )
    executor.register_mock_handler("search_knowledge", mock_handler)

    result = await executor.execute_step(_step(), {"query": "x"}, episode_id=new_id())
    assert result.status == "completed"
    assert result.output == "resultado mockeado"
    await executor.close()


@pytest.mark.asyncio
async def test_no_url_resolver_falls_back_to_simulation_not_crash():
    registry = InMemoryCapabilityRegistry()
    cap = Capability(
        name="future_capability", description="Servicio aún no desplegado", parameters_schema={},
        provider_service="whatsapp", endpoint_path="/api/v1/comms/send",
    )
    await registry.register([cap])

    executor = CapabilityExecutor(registry)  # sin resolver -> ningún servicio conocido
    result = await executor.execute_step(
        _step(capability_name="future_capability"), {"text": "hola"}, episode_id=new_id(),
    )

    assert result.status == "completed"
    assert "Simulación" in result.output
    await executor.close()
