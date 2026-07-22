from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# /health nunca exige API key: lo consultan healthchecks de Docker, que no envían encabezados
# de auth (mismo criterio que el resto de los servicios internos, ver gateway/src/main.py).
_PUBLIC_PATHS = {"/health"}


class ApiKeyAuthMiddleware:
    """
    Defensa en profundidad (F4-T2): el Gateway (F3-T1) ya autentica antes de proxyar hacia el
    servidor MCP, pero un acceso directo al transporte HTTP también debe exigir credencial —
    ningún servicio interno de MindOS debería confiar únicamente en el perímetro.
    """
    def __init__(self, app: ASGIApp, api_key: str):
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in _PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        provided = headers.get(b"x-api-key", b"").decode()
        if provided != self.api_key:
            response = JSONResponse({"detail": "Credenciales inválidas o ausentes."}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
