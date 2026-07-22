"""
F3-T1: el Gateway es el único punto de entrada seguro — sin credencial válida, 401; con
credencial válida (API key o JWT), rutea y responde. Cubre también correlation_id,
rate-limit, límite de tamaño de payload, `/health` agregado y ruteo por prefijo de servicio.
"""
import httpx
import pytest
from fastapi.testclient import TestClient

from gateway.src import main as gateway_main
from gateway.src.application.services.security import hash_password
from gateway.src.infrastructure.adapters.in_memory_rate_limiter import InMemoryRateLimiter


def _fake_downstream_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    if request.url.path == "/api/v1/memory/ping":
        return httpx.Response(200, json={"pong": True, "query": dict(request.url.params)})
    if request.url.path == "/api/v1/agents/execute":
        return httpx.Response(200, json={"executed": True})
    return httpx.Response(404, json={"detail": "no encontrado en el fake downstream"})


def _patch_gateway(monkeypatch, rate_limit_requests=1000):
    monkeypatch.setattr(gateway_main.settings, "MINDOS_API_KEY", "test-api-key")
    monkeypatch.setattr(gateway_main.settings, "MINDOS_ADMIN_USERNAME", "damian")
    monkeypatch.setattr(
        gateway_main.settings, "MINDOS_ADMIN_PASSWORD_HASH", hash_password("correcta-123")
    )
    monkeypatch.setattr(gateway_main.settings, "JWT_SECRET", "un-secreto-de-prueba-bien-largo-de-mas-de-32-bytes")
    monkeypatch.setattr(gateway_main.settings, "RATE_LIMIT_REQUESTS", rate_limit_requests)
    monkeypatch.setattr(gateway_main.settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(gateway_main.settings, "MAX_BODY_BYTES", 10 * 1024 * 1024)
    monkeypatch.setattr(gateway_main, "rate_limiter", InMemoryRateLimiter())

    async def override_http_client():
        async with httpx.AsyncClient(transport=httpx.MockTransport(_fake_downstream_handler)) as client:
            yield client
    gateway_main.app.dependency_overrides[gateway_main.get_http_client] = override_http_client


def _clear_overrides():
    gateway_main.app.dependency_overrides.clear()


def test_proxy_without_credentials_is_rejected(monkeypatch):
    _patch_gateway(monkeypatch)
    client = TestClient(gateway_main.app)
    try:
        resp = client.get("/api/v1/memory/ping")
        assert resp.status_code == 401
    finally:
        _clear_overrides()


def test_proxy_with_wrong_api_key_is_rejected(monkeypatch):
    _patch_gateway(monkeypatch)
    client = TestClient(gateway_main.app)
    try:
        resp = client.get("/api/v1/memory/ping", headers={"X-Api-Key": "clave-incorrecta"})
        assert resp.status_code == 401
    finally:
        _clear_overrides()


def test_proxy_with_correct_api_key_routes_to_memory(monkeypatch):
    _patch_gateway(monkeypatch)
    client = TestClient(gateway_main.app)
    try:
        resp = client.get(
            "/api/v1/memory/ping", params={"q": "hola"}, headers={"X-Api-Key": "test-api-key"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"pong": True, "query": {"q": "hola"}}
    finally:
        _clear_overrides()


def test_login_then_use_jwt_to_reach_agents(monkeypatch):
    _patch_gateway(monkeypatch)
    client = TestClient(gateway_main.app)
    try:
        login_resp = client.post(
            "/api/v1/auth/login", json={"username": "damian", "password": "correcta-123"}
        )
        assert login_resp.status_code == 200, login_resp.text
        token = login_resp.json()["access_token"]

        resp = client.post(
            "/api/v1/agents/execute", params={"goal": "hola"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"executed": True}
    finally:
        _clear_overrides()


def test_login_with_wrong_password_is_rejected(monkeypatch):
    _patch_gateway(monkeypatch)
    client = TestClient(gateway_main.app)
    try:
        resp = client.post(
            "/api/v1/auth/login", json={"username": "damian", "password": "incorrecta"}
        )
        assert resp.status_code == 401
    finally:
        _clear_overrides()


def test_unknown_service_prefix_returns_404(monkeypatch):
    _patch_gateway(monkeypatch)
    client = TestClient(gateway_main.app)
    try:
        resp = client.get("/api/v1/unknown-service/ping", headers={"X-Api-Key": "test-api-key"})
        assert resp.status_code == 404
    finally:
        _clear_overrides()


def test_health_aggregates_downstream_without_requiring_auth(monkeypatch):
    _patch_gateway(monkeypatch)
    client = TestClient(gateway_main.app)
    try:
        resp = client.get("/health")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert body["downstream"] == {"memory": "ok", "agents": "ok", "comms": "ok", "mcp": "ok"}
    finally:
        _clear_overrides()


def test_correlation_id_is_echoed_back_when_provided(monkeypatch):
    _patch_gateway(monkeypatch)
    client = TestClient(gateway_main.app)
    try:
        my_id = "018b10f8-e1a5-7b18-b2a6-382a93414900"
        resp = client.get("/health", headers={"X-Correlation-Id": my_id})
        assert resp.headers["x-correlation-id"] == my_id
    finally:
        _clear_overrides()


def test_correlation_id_is_generated_when_absent(monkeypatch):
    _patch_gateway(monkeypatch)
    client = TestClient(gateway_main.app)
    try:
        resp = client.get("/health")
        assert resp.headers.get("x-correlation-id"), "debe generar un correlation_id aunque el cliente no envíe uno"
    finally:
        _clear_overrides()


def test_rate_limit_blocks_after_exceeding_the_window(monkeypatch):
    _patch_gateway(monkeypatch, rate_limit_requests=2)
    client = TestClient(gateway_main.app)
    try:
        assert client.get("/health").status_code == 200
        assert client.get("/health").status_code == 200
        third = client.get("/health")
        assert third.status_code == 429
    finally:
        _clear_overrides()


def test_oversized_payload_is_rejected_before_routing(monkeypatch):
    _patch_gateway(monkeypatch)
    monkeypatch.setattr(gateway_main.settings, "MAX_BODY_BYTES", 10)
    client = TestClient(gateway_main.app)
    try:
        resp = client.post(
            "/api/v1/agents/execute", headers={"X-Api-Key": "test-api-key"},
            content=b"x" * 1000,
        )
        assert resp.status_code == 413
    finally:
        _clear_overrides()


@pytest.mark.parametrize(
    "service_key,base_url_attr",
    [("memory", "MEMORY_URL"), ("agents", "AGENTS_URL"), ("comms", "COMMS_URL"), ("mcp", "MCP_URL")],
)
def test_service_routes_cover_expected_services(service_key, base_url_attr):
    from gateway.src.config import SERVICE_ROUTES, settings
    assert SERVICE_ROUTES[service_key] == getattr(settings, base_url_attr)
    assert SERVICE_ROUTES["approvals"] == settings.AGENTS_URL


def test_cors_allows_the_dashboard_origin_including_on_error_responses(monkeypatch):
    """F4-T1: el Dashboard llama al Gateway desde su propio origen — sin el header CORS el
    navegador bloquea la respuesta aunque la petición esté bien autenticada. Debe estar
    presente incluso en una respuesta 401 (el navegador necesita verlo para no tratarlo como
    un fallo de red opaco)."""
    _patch_gateway(monkeypatch)
    monkeypatch.setattr(gateway_main.settings, "DASHBOARD_URL", "http://localhost:3000")
    client = TestClient(gateway_main.app)
    try:
        resp = client.options(
            "/api/v1/memory/ping",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-api-key",
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"

        unauth = client.get("/api/v1/memory/ping", headers={"Origin": "http://localhost:3000"})
        assert unauth.status_code == 401
        assert unauth.headers["access-control-allow-origin"] == "http://localhost:3000"
    finally:
        _clear_overrides()


def test_cors_rejects_an_unconfigured_origin():
    client = TestClient(gateway_main.app)
    resp = client.options(
        "/api/v1/memory/ping",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in resp.headers
