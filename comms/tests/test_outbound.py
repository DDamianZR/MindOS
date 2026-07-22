"""
F3-T7: entrega de mensajes salientes — el agente/Memory llama esto cuando un episodio con
`reply_to` concluye o cuando una capacidad queda pendiente de aprobación. Solo WhatsApp tiene
entrega bidireccional real hoy; CLI/REST se registran como "sin canal" sin fallar la petición.
"""
from fastapi.testclient import TestClient

from comms.src import main as comms_main


class _RecordingBus:
    def __init__(self):
        self.published = []

    async def publish(self, stream_name, event_type, event_data, correlation_id):
        self.published.append({"stream": stream_name, "type": event_type, "data": event_data})
        return "0-1"

    async def close(self):
        pass


class _FakeWhatsAppChannel:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.calls = []

    async def send(self, recipient_id, text):
        self.calls.append((recipient_id, text))
        if self.should_fail:
            raise ConnectionError("WhatsApp no disponible (simulado)")
        return {"status": "sent"}


def test_outbound_to_whatsapp_delivers_via_the_channel_and_publishes_an_event(monkeypatch):
    bus = _RecordingBus()
    channel = _FakeWhatsAppChannel()
    monkeypatch.setattr(comms_main, "event_bus", bus)
    monkeypatch.setattr(comms_main, "outbound_channels", {"whatsapp": channel})

    client = TestClient(comms_main.app)
    resp = client.post("/api/v1/comms/outbound", json={
        "provider": "whatsapp", "recipient_id": "5215512345678", "text": "El puerto es 443.",
    })

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["delivered"] is True
    assert body["status"] == "sent"

    assert channel.calls == [("5215512345678", "El puerto es 443.")]
    assert len(bus.published) == 1
    assert bus.published[0]["type"] == "com.mindos.communication.message.sent"
    assert bus.published[0]["data"].status == "sent"


def test_outbound_to_a_capture_only_channel_does_not_fail(monkeypatch):
    """F3-T3: CLI/REST no tienen entrega bidireccional — no es un error, solo no hay nada que hacer."""
    bus = _RecordingBus()
    monkeypatch.setattr(comms_main, "event_bus", bus)
    monkeypatch.setattr(comms_main, "outbound_channels", {"whatsapp": _FakeWhatsAppChannel()})

    client = TestClient(comms_main.app)
    resp = client.post("/api/v1/comms/outbound", json={
        "provider": "cli", "recipient_id": "cli-local", "text": "resultado de la pregunta",
    })

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["delivered"] is False
    assert body["status"] == "no_channel"


def test_outbound_channel_failure_is_reported_but_does_not_raise(monkeypatch):
    bus = _RecordingBus()
    monkeypatch.setattr(comms_main, "event_bus", bus)
    monkeypatch.setattr(comms_main, "outbound_channels", {"whatsapp": _FakeWhatsAppChannel(should_fail=True)})

    client = TestClient(comms_main.app)
    resp = client.post("/api/v1/comms/outbound", json={
        "provider": "whatsapp", "recipient_id": "5215512345678", "text": "hola",
    })

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["delivered"] is False
    assert body["status"] == "failed"
    assert bus.published[0]["data"].status == "failed"


def test_outbound_generates_a_message_id_when_absent(monkeypatch):
    monkeypatch.setattr(comms_main, "event_bus", _RecordingBus())
    monkeypatch.setattr(comms_main, "outbound_channels", {"whatsapp": _FakeWhatsAppChannel()})

    client = TestClient(comms_main.app)
    resp = client.post("/api/v1/comms/outbound", json={
        "provider": "whatsapp", "recipient_id": "5215512345678", "text": "hola",
    })
    assert resp.json()["message_id"]
