"""F4-T2: defensa en profundidad del transporte HTTP — /health nunca exige API key
(lo consultan healthchecks de Docker), el resto de rutas sí."""
from mindos_mcp.auth_middleware import ApiKeyAuthMiddleware
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


async def _health(request):
    return JSONResponse({"status": "ok"})


async def _mcp_endpoint(request):
    return JSONResponse({"tool": "called"})


def _wrapped_app(api_key: str) -> ApiKeyAuthMiddleware:
    inner = Starlette(routes=[
        Route("/health", _health, methods=["GET"]),
        Route("/mcp", _mcp_endpoint, methods=["POST"]),
    ])
    return ApiKeyAuthMiddleware(inner, api_key)


def test_health_never_requires_an_api_key():
    client = TestClient(_wrapped_app("secret-key"))
    resp = client.get("/health")
    assert resp.status_code == 200


def test_protected_route_rejects_missing_api_key():
    client = TestClient(_wrapped_app("secret-key"))
    resp = client.post("/mcp")
    assert resp.status_code == 401


def test_protected_route_rejects_wrong_api_key():
    client = TestClient(_wrapped_app("secret-key"))
    resp = client.post("/mcp", headers={"X-Api-Key": "wrong"})
    assert resp.status_code == 401


def test_protected_route_accepts_the_correct_api_key():
    client = TestClient(_wrapped_app("secret-key"))
    resp = client.post("/mcp", headers={"X-Api-Key": "secret-key"})
    assert resp.status_code == 200
    assert resp.json() == {"tool": "called"}
