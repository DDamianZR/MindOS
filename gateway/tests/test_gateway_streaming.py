"""
F7-T5: el Gateway reenvía las respuestas `text/event-stream` (chat del asistente) evento a evento
en vez de bufferizarlas, con la misma autenticación que cualquier otra ruta.
"""
import httpx
from fastapi.testclient import TestClient

from gateway.src import main as gateway_main
from gateway.tests.test_gateway import _clear_overrides, _patch_gateway

SSE_BODY = (
    b'event: conversation\ndata: {"conversation_id": "c1"}\n\n'
    b'event: text\ndata: {"type": "text", "text": "Hola"}\n\n'
    b'event: done\ndata: {"type": "done"}\n\n'
)
AUTH = {"X-Api-Key": "test-api-key"}
STREAM = {**AUTH, "Accept": "text/event-stream"}


class _BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'event: text\ndata: {"type": "text", "text": "Ho"}\n\n'
        raise httpx.ReadError("conexión cortada")


def _patch_stream_downstream(seen: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path == "/api/v1/agents/assistant/chat":
            return httpx.Response(200, headers={"content-type": "text/event-stream; charset=utf-8"}, content=SSE_BODY)
        if path == "/api/v1/agents/assistant/broken":
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=_BrokenStream())
        if path == "/api/v1/agents/assistant/down":
            raise httpx.ConnectError("sin servicio")
        return httpx.Response(404, json={"detail": "Esa conversación ya no existe."})

    gateway_main.app.dependency_overrides[gateway_main.get_stream_client_factory] = (
        lambda: lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


def test_event_stream_is_relayed_with_its_content_type(monkeypatch):
    _patch_gateway(monkeypatch)
    seen: list[httpx.Request] = []
    _patch_stream_downstream(seen)
    client = TestClient(gateway_main.app)
    try:
        with client.stream(
            "POST", "/api/v1/agents/assistant/chat", json={"message": "Hola"}, headers=STREAM,
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            assert "x-correlation-id" in resp.headers
            body = b"".join(resp.iter_raw())

        assert body == SSE_BODY
        assert seen[0].method == "POST" and b"Hola" in seen[0].content
        assert "x-correlation-id" in seen[0].headers
    finally:
        _clear_overrides()


def test_streaming_route_still_requires_credentials(monkeypatch):
    _patch_gateway(monkeypatch)
    seen: list[httpx.Request] = []
    _patch_stream_downstream(seen)
    client = TestClient(gateway_main.app)
    try:
        resp = client.post(
            "/api/v1/agents/assistant/chat", json={"message": "Hola"}, headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 401
        assert seen == [], "sin credencial no se llega a tocar el downstream"
    finally:
        _clear_overrides()


def test_non_stream_reply_to_a_stream_request_keeps_its_status_and_body(monkeypatch):
    """Un 404 en JSON del downstream debe llegar como 404 en JSON, no como un stream vacío."""
    _patch_gateway(monkeypatch)
    _patch_stream_downstream([])
    client = TestClient(gateway_main.app)
    try:
        resp = client.post("/api/v1/agents/assistant/otra", json={"message": "Hola"}, headers=STREAM)
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Esa conversación ya no existe."}
    finally:
        _clear_overrides()


def test_unreachable_downstream_on_a_stream_request_is_a_502(monkeypatch):
    _patch_gateway(monkeypatch)
    _patch_stream_downstream([])
    client = TestClient(gateway_main.app)
    try:
        resp = client.post("/api/v1/agents/assistant/down", json={}, headers=STREAM)
        assert resp.status_code == 502
    finally:
        _clear_overrides()


def test_stream_cut_midway_ends_with_an_error_event(monkeypatch):
    _patch_gateway(monkeypatch)
    _patch_stream_downstream([])
    client = TestClient(gateway_main.app)
    try:
        resp = client.post("/api/v1/agents/assistant/broken", json={}, headers=STREAM)
        assert resp.status_code == 200
        assert resp.text.startswith("event: text")
        assert resp.text.rstrip().split("\n\n")[-1].startswith("event: error")
    finally:
        _clear_overrides()


def test_requests_without_the_stream_accept_header_use_the_buffered_path(monkeypatch):
    _patch_gateway(monkeypatch)
    seen: list[httpx.Request] = []
    _patch_stream_downstream(seen)
    client = TestClient(gateway_main.app)
    try:
        resp = client.get("/api/v1/memory/ping", params={"q": "hola"}, headers=AUTH)
        assert resp.status_code == 200 and resp.json()["pong"] is True
        assert seen == [], "el cliente de streaming no se usa"
    finally:
        _clear_overrides()
