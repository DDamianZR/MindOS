"""
Cierre de Fase 3 — verificación integral end-to-end (plan/03-gateway-comunicacion.md):
"MindOS ya captura desde el mundo real y responde por el mismo canal, con todo lo capturado
convertido en conocimiento indexado, enlazado y trazable."

A diferencia de los smoke tests de Fase 1/2 (que solo encadenaban Memory+Agents), este cierra
el círculo pasando por el ÚNICO PUNTO DE ENTRADA real (Gateway, F3-T1): autenticado, ruteado a
Memory/Agents/Comms real in-process. No repite la cobertura ya exhaustiva de cada tarea
(`test_ingestion_pipeline.py` con 11 tests, `test_outbound.py`, `test_approvals_router.py`,
`test_cli_rest_parity.py`, etc.) — prueba específicamente las COSTURAS entre servicios que solo
existen cuando se accede por el camino real, no por llamadas directas a cada servicio aislado.

Sin Redis real en este entorno de desarrollo, el "consumidor" del pipeline se dispara a mano
con el evento que `comms` publicó — mismo patrón que `test_ingestion_pipeline.py`.
"""
import asyncio

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
from comms.src import main as comms_main
from comms.src.infrastructure.adapters.event_bus_inbound_handler import EventBusInboundHandler
from gateway.src import main as gateway_main
from gateway.src.infrastructure.adapters.in_memory_rate_limiter import InMemoryRateLimiter
from memory.src import main as memory_main
from memory.src.application.services.ingestion_pipeline import IngestionPipelineService
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_storage import InMemoryStorage
from memory.src.infrastructure.adapters.in_memory_thinking_graph import InMemoryThinkingGraph
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding
from memory.src.infrastructure.adapters.mock_ocr import MockOcr
from memory.src.infrastructure.adapters.mock_stt import MockStt


class _NoopBus:
    async def publish(self, *args, **kwargs):
        return "0-1"

    async def close(self):
        pass


class _RecordingBus:
    """Como _NoopBus, pero guarda lo publicado — para poder disparar el pipeline a mano
    (bridge manual del consumidor, ya que no hay Redis real en este entorno)."""
    def __init__(self):
        self.published = []

    async def publish(self, stream_name, event_type, event_data, correlation_id):
        # Mismo formato de wire que RedisEventBus.publish (data como JSON string, no el objeto
        # Pydantic crudo) — el pipeline espera exactamente esta forma (model_validate_json).
        self.published.append({
            "stream": stream_name, "type": event_type,
            "data": event_data.model_dump_json(), "correlation_id": str(correlation_id),
        })
        return "0-1"

    async def close(self):
        pass


class _HostRoutingTransport(httpx.AsyncBaseTransport):
    """`httpx.AsyncClient` solo acepta un `transport`; este test necesita que UN cliente
    compartido (el de Gateway, o el de Agents) alcance varias apps ASGI reales distintas.
    Enruta por el host del URL — cada servicio downstream usa un hostname de prueba propio."""
    def __init__(self, apps_by_host: dict):
        self._transports = {host: httpx.ASGITransport(app=app) for host, app in apps_by_host.items()}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        transport = self._transports.get(request.url.host)
        if not transport:
            return httpx.Response(502, json={"detail": f"host no ruteado en el test: {request.url.host}"})
        return await transport.handle_async_request(request)


def _wire_all_services(monkeypatch):
    # Memory: estado limpio + proveedores mock/en-memoria.
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", InMemoryDatabase())
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    monkeypatch.setattr(memory_main, "in_memory_thinking_graph", InMemoryThinkingGraph())

    # Comms: bus que registra lo publicado, para poder disparar el pipeline a mano.
    comms_bus = _RecordingBus()
    monkeypatch.setattr(comms_main, "event_bus", comms_bus)
    monkeypatch.setattr(
        comms_main, "inbound_handler", EventBusInboundHandler(comms_bus, comms_main.settings.INBOUND_STREAM)
    )

    # Agents: registro y aprobaciones limpios.
    registry = InMemoryCapabilityRegistry()
    approval_store = InMemoryApprovalStore()
    monkeypatch.setattr(agents_main, "capability_registry", registry)
    monkeypatch.setattr(agents_main, "approval_store", approval_store)

    # Gateway: auth + rate-limit conocidos y sin límite práctico para el test.
    monkeypatch.setattr(gateway_main.settings, "MINDOS_API_KEY", "test-api-key")
    monkeypatch.setattr(gateway_main.settings, "RATE_LIMIT_REQUESTS", 1000)
    monkeypatch.setattr(gateway_main, "rate_limiter", InMemoryRateLimiter())

    # Las tres apps reales, alcanzables por hostname de prueba bajo un único transporte. Tanto
    # el proxy (SERVICE_ROUTES) como `/health` (que lee MEMORY_URL/AGENTS_URL/COMMS_URL de
    # settings directamente, no de SERVICE_ROUTES) necesitan apuntar a los mismos hostnames.
    apps_by_host = {"memory-svc": memory_main.app, "agents-svc": agents_main.app, "comms-svc": comms_main.app}
    monkeypatch.setattr(gateway_main.settings, "MEMORY_URL", "http://memory-svc")
    monkeypatch.setattr(gateway_main.settings, "AGENTS_URL", "http://agents-svc")
    monkeypatch.setattr(gateway_main.settings, "COMMS_URL", "http://comms-svc")
    monkeypatch.setattr(gateway_main, "SERVICE_ROUTES", {
        "memory": "http://memory-svc", "agents": "http://agents-svc",
        "comms": "http://comms-svc", "approvals": "http://agents-svc",
    })

    async def override_gateway_http_client():
        async with httpx.AsyncClient(transport=_HostRoutingTransport(apps_by_host)) as client:
            yield client
    gateway_main.app.dependency_overrides[gateway_main.get_http_client] = override_gateway_http_client

    return registry, approval_store, comms_bus


def _auth_headers():
    return {"X-Api-Key": "test-api-key"}


def test_capture_via_gateway_reaches_comms_and_pipeline_indexes_it_with_provenance(monkeypatch):
    """El único punto de entrada (Gateway) autentica, rutea a comms, comms publica el evento
    real, y el pipeline (disparado a mano, sin Redis real) indexa el conocimiento con
    provenance real — recuperable, también, consultando de vuelta a través del Gateway."""
    _wire_all_services(monkeypatch)
    pipeline = IngestionPipelineService(
        memory_client=httpx.AsyncClient(transport=httpx.ASGITransport(app=memory_main.app), base_url="http://memory"),
        agents_client=httpx.AsyncClient(transport=httpx.ASGITransport(app=agents_main.app)),
        storage=InMemoryStorage(), ocr=MockOcr(), stt=MockStt(), llm=agents_main.MockLlm(),
    )

    gateway_client = TestClient(gateway_main.app)
    try:
        capture_resp = gateway_client.post(
            "/api/v1/comms/inbound", headers=_auth_headers(), json={
                "provider": "rest", "sender_id": "user-1", "recipient_id": "mindos",
                "text": "El puerto configurado para TLS es 443.",
            },
        )
        assert capture_resp.status_code == 201, capture_resp.text

        # Bridge manual del consumidor (sin Redis real): el pipeline procesa lo que comms
        # publicó, tal como lo haría RedisEventBus.subscribe en producción.
        comms_bus = comms_main.event_bus
        assert len(comms_bus.published) == 1
        asyncio.run(pipeline.handle_event(comms_bus.published[0]))

        search_resp = gateway_client.post(
            "/api/v1/memory/search", headers=_auth_headers(), params={"query": "puerto configurado TLS"},
        )
        assert search_resp.status_code == 200, search_resp.text
        results = search_resp.json()["results"]
        node = next(r for r in results if "443" in r["content"])

        provenance_resp = gateway_client.get(
            f"/api/v1/memory/node/{node['node_id']}/provenance", headers=_auth_headers(),
        )
        assert provenance_resp.status_code == 200
        source = provenance_resp.json()["chain"][0]["source"]
        assert source["kind"] == "api"  # provider="rest" -> SourceKind.API (F3-T5)
    finally:
        gateway_main.app.dependency_overrides.clear()


def test_capture_via_gateway_without_credentials_is_rejected(monkeypatch):
    """"Único punto de entrada SEGURO": sin API key ni JWT, ni comms ni memory son alcanzables."""
    _wire_all_services(monkeypatch)
    gateway_client = TestClient(gateway_main.app)
    try:
        resp = gateway_client.post("/api/v1/comms/inbound", json={
            "provider": "rest", "sender_id": "user-1", "text": "esto no debería capturarse",
        })
        assert resp.status_code == 401
    finally:
        gateway_main.app.dependency_overrides.clear()


def test_sensitive_capability_pauses_and_resolves_via_gateway_approvals_endpoint(monkeypatch):
    """"approvals" no es un servicio propio (F3-T1): el Gateway lo mapea a Agents. Aprobar por
    ahí despacha la capacidad diferida — DoD F3-T7: "solo procede tras el sí"."""
    registry, approval_store, _ = _wire_all_services(monkeypatch)

    episode_id = new_id()
    memory_client = TestClient(memory_main.app)
    ep_resp = memory_client.post("/api/v1/thinking/episodes", json={
        "episode_id": str(episode_id), "goal": "Acción sensible", "correlation_id": str(episode_id),
        "agent": "AgentsService",
    })
    assert ep_resp.status_code == 201, ep_resp.text

    async def _seed_pending_approval():
        cap = Capability(
            name="delete_all_memory", description="Acción destructiva", parameters_schema={},
            provider_service="whatsapp", endpoint_path="/api/v1/x", requires_approval=True,
        )
        await registry.register([cap])
        executor = CapabilityExecutor(registry, approval_store=approval_store)
        step = PlanStep(step_id=1, task="borrar todo", capability_name="delete_all_memory",
                         expected_output="ok", status="pending")
        return await executor.execute_step(step, {"confirm": "yes"}, episode_id=episode_id)

    result = asyncio.run(_seed_pending_approval())
    approval_id = result.output.split("approval_id=")[1].strip()

    # El router de aprobaciones (montado en Agents) resuelve SU PROPIO get_http_client para
    # llegar a Memory (recorder + _next_step_index) — un override aparte del de Gateway, ya
    # que la petición, al llegar a Agents vía el ASGITransport del Gateway, entra por el
    # pipeline de dependencias real de Agents, no el de Gateway.
    async def override_agents_http_client():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=memory_main.app)) as client:
            yield client
    agents_main.app.dependency_overrides[agents_main.get_http_client] = override_agents_http_client

    gateway_client = TestClient(gateway_main.app)
    try:
        get_resp = gateway_client.get(f"/api/v1/approvals/{approval_id}", headers=_auth_headers())
        assert get_resp.status_code == 200, get_resp.text
        assert get_resp.json()["status"] == "pending"

        with gateway_client:
            resolve_resp = gateway_client.post(
                f"/api/v1/approvals/{approval_id}/resolve", headers=_auth_headers(), json={"approved": True},
            )
        assert resolve_resp.status_code == 200, resolve_resp.text
        body = resolve_resp.json()
        assert body["executed"] is True
        assert body["approval"]["status"] == "approved"
        assert "Simulación" in body["approval"]["result_output"]  # whatsapp no resuelve a URL -> simula limpio
    finally:
        gateway_main.app.dependency_overrides.clear()
        agents_main.app.dependency_overrides.clear()


def test_gateway_health_aggregates_the_three_real_services(monkeypatch):
    _wire_all_services(monkeypatch)
    gateway_client = TestClient(gateway_main.app)
    try:
        resp = gateway_client.get("/health")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert body["downstream"] == {"memory": "ok", "agents": "ok", "comms": "ok"}
    finally:
        gateway_main.app.dependency_overrides.clear()
