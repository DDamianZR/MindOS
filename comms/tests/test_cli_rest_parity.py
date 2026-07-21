"""
F3-T3 DoD: "capturar por CLI y por REST produce el mismo evento en el stream; un test lo
verifica." La CLI llama al MISMO endpoint que el adaptador REST (in-process vía ASGITransport,
sin red real) — este test confirma que ambos caminos terminan en un evento estructuralmente
idéntico (mismo stream, mismo tipo, mismos campos), difiriendo solo en lo que genuinamente
distingue el origen (provider, sender_id, message_id).
"""
import asyncio

import httpx
from fastapi.testclient import TestClient

from comms.src import cli as comms_cli
from comms.src import main as comms_main
from comms.src.infrastructure.adapters.event_bus_inbound_handler import EventBusInboundHandler


class _RecordingBus:
    def __init__(self):
        self.published = []

    async def publish(self, stream_name, event_type, event_data, correlation_id):
        self.published.append({"stream": stream_name, "type": event_type, "data": event_data})
        return "0-1"

    async def close(self):
        pass


def test_cli_and_rest_capture_produce_the_same_shaped_event(monkeypatch):
    bus = _RecordingBus()
    monkeypatch.setattr(
        comms_main, "inbound_handler", EventBusInboundHandler(bus, comms_main.settings.INBOUND_STREAM)
    )

    same_text = "Idea: cachear las consultas frecuentes de reportes."

    # REST
    rest_client = TestClient(comms_main.app)
    rest_resp = rest_client.post("/api/v1/comms/inbound", json={
        "provider": "rest", "sender_id": "user-1", "recipient_id": "mindos", "text": same_text,
    })
    assert rest_resp.status_code == 201, rest_resp.text

    # CLI: mismo proceso, mismo endpoint, alcanzado in-process vía ASGITransport (sin red real).
    async def _run_cli():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=comms_main.app)) as client:
            return await comms_cli.capture(same_text, client=client, base_url="http://comms")
    cli_result = asyncio.run(_run_cli())
    assert cli_result["status"] == "received"

    assert len(bus.published) == 2
    rest_event, cli_event = bus.published[0], bus.published[1]

    # Mismo stream y mismo tipo de evento para ambos orígenes.
    assert rest_event["stream"] == cli_event["stream"] == comms_main.settings.INBOUND_STREAM
    assert rest_event["type"] == cli_event["type"] == "com.mindos.communication.message.received"

    rest_data, cli_data = rest_event["data"], cli_event["data"]
    # Mismo contenido y misma forma (mismos campos) — difieren solo en lo que genuinamente
    # distingue el canal de origen: provider, sender_id, message_id (cada captura genera el suyo).
    assert rest_data.text == cli_data.text == same_text
    assert set(rest_data.model_dump().keys()) == set(cli_data.model_dump().keys())
    assert rest_data.provider == "rest"
    assert cli_data.provider == "cli"
    assert rest_data.message_id != cli_data.message_id
