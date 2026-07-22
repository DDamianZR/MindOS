"""
F3-T7: "el agente responde por el mismo canal" — cuando un goal viene con `reply_to` (F3-T5,
el pipeline lo pasa si el mensaje venía de un canal bidireccional), el resultado final se
entrega vía `POST /api/v1/comms/outbound`, no solo se guarda en el Knowledge Graph.

Usa un Memory Service real in-process (ASGITransport, igual que test_reasoning_trace_integration)
para el flujo normal del agente, y una app FastAPI mínima que solo registra las llamadas a
/api/v1/comms/outbound — un `_RoutingTransport` decide cuál de las dos according al path.
"""
import asyncio

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mindos_schemas.capabilities import Capability

from agents.src import main as agents_main
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


class _RoutingTransport(httpx.AsyncBaseTransport):
    """Enruta por prefijo de path a uno de varios transportes ASGI — necesario porque
    `httpx.AsyncClient` solo acepta un `transport`, y este test necesita dos apps distintas
    (Memory real + un stub de comms) detrás del MISMO cliente compartido de Agents."""
    def __init__(self, routes: dict[str, httpx.AsyncBaseTransport], default: httpx.AsyncBaseTransport):
        self.routes = routes
        self.default = default

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        for prefix, transport in self.routes.items():
            if request.url.path.startswith(prefix):
                return await transport.handle_async_request(request)
        return await self.default.handle_async_request(request)


def _build_fake_comms_app(calls: list):
    app = FastAPI()

    @app.post("/api/v1/comms/outbound")
    async def outbound(request: dict):
        calls.append(request)
        return {"status": "sent", "message_id": "x", "provider": request["provider"], "delivered": True}

    return app


def _wire_memory(monkeypatch):
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", InMemoryDatabase())
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    monkeypatch.setattr(memory_main, "in_memory_thinking_graph", InMemoryThinkingGraph())


def test_completed_episode_with_reply_to_notifies_the_origin_channel(monkeypatch):
    _wire_memory(monkeypatch)
    memory_client = TestClient(memory_main.app)

    seed = memory_client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "Config de Traefik",
        "content": "El puerto configurado para TLS es 443.", "author": "damian",
    })
    assert seed.status_code == 201, seed.text

    registry = InMemoryCapabilityRegistry()
    monkeypatch.setattr(agents_main, "capability_registry", registry)

    async def _register():
        await registry.register([
            Capability(
                name="search_knowledge", description="Busca en memoria",
                parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                provider_service="memory", endpoint_path="/api/v1/memory/search",
            ),
            Capability(
                name="send_chat_message", description="Envía un mensaje", parameters_schema={},
                provider_service="communication", endpoint_path="/api/v1/communication/send",
            ),
        ])
    asyncio.run(_register())

    outbound_calls: list = []
    fake_comms_app = _build_fake_comms_app(outbound_calls)
    routing_transport = _RoutingTransport(
        routes={"/api/v1/comms": httpx.ASGITransport(app=fake_comms_app)},
        default=httpx.ASGITransport(app=memory_main.app),
    )

    async def override_http_client():
        async with httpx.AsyncClient(transport=routing_transport) as client:
            yield client
    agents_main.app.dependency_overrides[agents_main.get_http_client] = override_http_client

    agents_client = TestClient(agents_main.app)
    try:
        resp = agents_client.post(
            "/api/v1/agents/execute",
            params={
                "goal": "puerto configurado para TLS",
                "reply_to_provider": "whatsapp", "reply_to_sender_id": "5215512345678",
            },
        )
        assert resp.status_code == 200, resp.text
    finally:
        agents_main.app.dependency_overrides.clear()

    assert len(outbound_calls) == 1
    notified = outbound_calls[0]
    assert notified["provider"] == "whatsapp"
    assert notified["recipient_id"] == "5215512345678"
    assert notified["text"]  # el final_output del agente, no vacío


def test_episode_without_reply_to_does_not_call_comms(monkeypatch):
    """Sin canal de origen (ej: goal disparado sin pipeline detrás), no debe intentarse
    ninguna notificación saliente."""
    _wire_memory(monkeypatch)
    memory_client = TestClient(memory_main.app)
    memory_client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "Config", "content": "El puerto es 443.", "author": "damian",
    })

    registry = InMemoryCapabilityRegistry()
    monkeypatch.setattr(agents_main, "capability_registry", registry)

    async def _register():
        await registry.register([
            Capability(
                name="search_knowledge", description="Busca en memoria",
                parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                provider_service="memory", endpoint_path="/api/v1/memory/search",
            ),
            Capability(
                name="send_chat_message", description="Envía un mensaje", parameters_schema={},
                provider_service="communication", endpoint_path="/api/v1/communication/send",
            ),
        ])
    asyncio.run(_register())

    outbound_calls: list = []
    fake_comms_app = _build_fake_comms_app(outbound_calls)
    routing_transport = _RoutingTransport(
        routes={"/api/v1/comms": httpx.ASGITransport(app=fake_comms_app)},
        default=httpx.ASGITransport(app=memory_main.app),
    )

    async def override_http_client():
        async with httpx.AsyncClient(transport=routing_transport) as client:
            yield client
    agents_main.app.dependency_overrides[agents_main.get_http_client] = override_http_client

    agents_client = TestClient(agents_main.app)
    try:
        resp = agents_client.post("/api/v1/agents/execute", params={"goal": "puerto configurado"})
        assert resp.status_code == 200, resp.text
    finally:
        agents_main.app.dependency_overrides.clear()

    assert outbound_calls == []
