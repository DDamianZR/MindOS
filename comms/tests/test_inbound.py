"""F3-T3: capturar produce el mismo tipo de evento sin importar el canal (CLI/REST)."""
from fastapi.testclient import TestClient
from mindos_schemas.events.v1.communication_events import MessageReceivedEventData

from comms.src import main as comms_main
from comms.src.infrastructure.adapters.event_bus_inbound_handler import EventBusInboundHandler


class _RecordingBus:
    def __init__(self):
        self.published = []

    async def publish(self, stream_name, event_type, event_data, correlation_id):
        self.published.append({
            "stream": stream_name, "type": event_type, "data": event_data, "correlation_id": correlation_id,
        })
        return "0-1"

    async def close(self):
        pass


class _FailingBus:
    async def publish(self, *args, **kwargs):
        raise ConnectionError("Redis no disponible (simulado)")


def _wire(monkeypatch, bus=None):
    bus = bus or _RecordingBus()
    monkeypatch.setattr(
        comms_main, "inbound_handler", EventBusInboundHandler(bus, comms_main.settings.INBOUND_STREAM)
    )
    return bus


def test_rest_inbound_publishes_message_received_event(monkeypatch):
    bus = _wire(monkeypatch)
    client = TestClient(comms_main.app)

    resp = client.post("/api/v1/comms/inbound", json={
        "provider": "rest", "sender_id": "user-1", "recipient_id": "mindos", "text": "hola desde REST",
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "received"
    assert body["provider"] == "rest"

    assert len(bus.published) == 1
    event = bus.published[0]
    assert event["stream"] == comms_main.settings.INBOUND_STREAM
    assert event["type"] == "com.mindos.communication.message.received"
    assert isinstance(event["data"], MessageReceivedEventData)
    assert event["data"].text == "hola desde REST"
    assert event["data"].provider == "rest"
    assert event["data"].message_id == body["message_id"]


def test_rest_inbound_generates_message_id_when_absent(monkeypatch):
    bus = _wire(monkeypatch)
    client = TestClient(comms_main.app)
    resp = client.post("/api/v1/comms/inbound", json={
        "provider": "rest", "sender_id": "user-1", "text": "sin message_id",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["message_id"]
    assert bus.published[0]["data"].message_id == resp.json()["message_id"]


def test_inbound_fails_explicitly_when_event_bus_is_down(monkeypatch):
    """A diferencia de Memory (que tiene un event_log durable de respaldo en Postgres), aquí
    el evento en el bus ES el único registro del mensaje: si el bus falla, debe fallar
    explícito (503) en vez de reportar éxito y perder el mensaje en silencio."""
    _wire(monkeypatch, bus=_FailingBus())
    client = TestClient(comms_main.app)
    resp = client.post("/api/v1/comms/inbound", json={
        "provider": "rest", "sender_id": "user-1", "text": "este mensaje no debe perderse en silencio",
    })
    assert resp.status_code == 503


def test_health_ok():
    client = TestClient(comms_main.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
