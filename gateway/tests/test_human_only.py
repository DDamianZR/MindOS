"""
Las decisiones de human-in-the-loop (resolver una aprobación, activar una rutina propuesta por
el agente) solo las puede tomar una persona con JWT de sesión, nunca una API key de servicio.
"""
import httpx
from fastapi.testclient import TestClient

from gateway.src import main as gateway_main
from gateway.tests.test_gateway import _clear_overrides, _patch_gateway

SERVICE = {"X-Api-Key": "test-api-key"}


def _wire(monkeypatch, seen):
    _patch_gateway(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    async def override_http_client():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            yield client

    gateway_main.app.dependency_overrides[gateway_main.get_http_client] = override_http_client


def _human_token(client: TestClient) -> dict[str, str]:
    token = client.post("/api/v1/auth/login", json={"username": "damian", "password": "correcta-123"}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def test_service_key_cannot_resolve_an_approval_or_activate_a_routine(monkeypatch):
    seen: list[str] = []
    _wire(monkeypatch, seen)
    client = TestClient(gateway_main.app)
    try:
        for path in ["/api/v1/approvals/abc/resolve", "/api/v1/agents/routines/r1/activate"]:
            resp = client.post(path, json={"approved": True}, headers=SERVICE)
            assert resp.status_code == 403, path
            assert "persona" in resp.json()["detail"]
        assert seen == [], "nada llega al servicio interno"
    finally:
        _clear_overrides()


def test_a_person_with_a_session_can(monkeypatch):
    seen: list[str] = []
    _wire(monkeypatch, seen)
    client = TestClient(gateway_main.app)
    try:
        headers = _human_token(client)
        assert client.post("/api/v1/approvals/abc/resolve", json={"approved": True}, headers=headers).status_code == 200
        assert client.post("/api/v1/agents/routines/r1/activate", headers=headers).status_code == 200
        assert seen == ["/api/v1/approvals/abc/resolve", "/api/v1/agents/routines/r1/activate"]
    finally:
        _clear_overrides()


def test_service_key_keeps_everything_else(monkeypatch):
    seen: list[str] = []
    _wire(monkeypatch, seen)
    client = TestClient(gateway_main.app)
    try:
        assert client.get("/api/v1/approvals/abc", headers=SERVICE).status_code == 200
        assert client.post("/api/v1/agents/routines/r1/pause", headers=SERVICE).status_code == 200
        assert client.post("/api/v1/agents/routines", json={}, headers=SERVICE).status_code == 200
    finally:
        _clear_overrides()
