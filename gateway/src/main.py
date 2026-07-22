import asyncio
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mindos_common.context import clear_correlation_id, get_correlation_id, set_correlation_id
from mindos_common.ids import new_id
from mindos_common.logging import configure_logging, get_logger
from pydantic import BaseModel
from redis.asyncio import Redis

from gateway.src.application.services.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)
from gateway.src.config import SERVICE_ROUTES, settings
from gateway.src.infrastructure.adapters.in_memory_rate_limiter import InMemoryRateLimiter
from gateway.src.infrastructure.adapters.redis_rate_limiter import RedisRateLimiter

configure_logging("GatewayService", settings.MINDOS_ENV)
logger = get_logger("gateway_main")

app = FastAPI(
    title="MindOS Gateway",
    description="Único punto de entrada seguro de MindOS: auth, rate-limit y ruteo a los servicios internos",
    version="1.0.0",
)

# Hop-by-hop headers (RFC 7230 §6.1) + host: nunca se reenvían tal cual, cada lado (httpx al
# downstream, Starlette de vuelta al cliente) recalcula los suyos según el body real.
_HOP_BY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}

rate_limiter = (
    RedisRateLimiter(Redis.from_url(settings.REDIS_URL))
    if settings.RATE_LIMITER_TYPE == "redis" else InMemoryRateLimiter()
)


async def get_http_client():
    """Cliente HTTP compartido hacia los servicios downstream, inyectado vía `Depends`."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


async def require_auth(request: Request) -> str:
    """
    Auth mono-usuario (F3-T1): API key para llamadas servicio-a-servicio, o JWT Bearer para el
    humano (emitido por `/api/v1/auth/login`). Cualquiera de las dos basta.
    """
    api_key = request.headers.get("x-api-key")
    if api_key and api_key == settings.MINDOS_API_KEY:
        return "service"

    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        payload = decode_access_token(auth_header[7:], settings.JWT_SECRET, settings.JWT_ALGORITHM)
        if payload and payload.get("sub"):
            return payload["sub"]

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas o ausentes.")


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


@app.middleware("http")
async def correlation_and_rate_limit_middleware(request: Request, call_next):
    """
    Se ejecuta para TODA petición (incluidas `/health` y `/auth/login`, sin excepción — el
    rate-limit protege también el login contra fuerza bruta): origina/propaga el
    `X-Correlation-Id` y aplica el rate-limit por IP antes de tocar cualquier lógica de ruta.
    """
    incoming = request.headers.get("x-correlation-id")
    try:
        correlation_id = UUID(incoming) if incoming else new_id()
    except ValueError:
        correlation_id = new_id()
    token = set_correlation_id(correlation_id)

    try:
        client_ip = request.client.host if request.client else "unknown"
        try:
            within_limit = await rate_limiter.hit(
                client_ip, settings.RATE_LIMIT_REQUESTS, settings.RATE_LIMIT_WINDOW_SECONDS
            )
        except Exception as e:
            # Fail-open: perder el rate-limit por una caída de Redis es preferible a tumbar
            # todo el Gateway (disponibilidad > enforcement estricto en un sistema mono-usuario).
            logger.warning("Rate limiter no disponible, dejando pasar la petición", error=str(e))
            within_limit = True

        if not within_limit:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Demasiadas peticiones. Intenta de nuevo más tarde."},
                headers={"X-Correlation-Id": str(correlation_id)},
            )

        response = await call_next(request)
        response.headers["X-Correlation-Id"] = str(correlation_id)
        return response
    finally:
        clear_correlation_id(token)


# Registrado DESPUÉS del middleware de arriba a propósito: Starlette apila los middlewares en
# orden inverso de registro (el último añadido queda MÁS AFUERA), así que CORS queda envolviendo
# todo — incluidas las respuestas 401/429 que emite nuestro propio middleware — y el navegador
# recibe el header en cualquier caso, no solo en las respuestas felices.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.DASHBOARD_URL],
    allow_credentials=False,  # auth va por header Authorization/X-Api-Key, no por cookies
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health(http_client: httpx.AsyncClient = Depends(get_http_client)):
    """Agrega el estado de cada servicio downstream (F3-T1). Sin auth: lo consultan
    healthchecks de Docker/Traefik, no un cliente autenticado."""
    async def _check(name: str, base_url: str) -> tuple[str, str]:
        try:
            resp = await http_client.get(f"{base_url}/health", timeout=3.0)
            return name, ("ok" if resp.status_code == 200 else f"error:{resp.status_code}")
        except Exception as e:
            return name, f"unreachable:{type(e).__name__}"

    downstream_services = {
        "memory": settings.MEMORY_URL, "agents": settings.AGENTS_URL,
        "comms": settings.COMMS_URL, "mcp": settings.MCP_URL,
    }
    results = dict(await asyncio.gather(*(_check(name, url) for name, url in downstream_services.items())))
    overall = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    return {"status": overall, "service": "gateway", "downstream": results}


@app.post("/api/v1/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login mono-usuario (F3-T1): valida contra `MINDOS_ADMIN_USERNAME` + hash Argon2 en .env,
    emite un JWT de sesión. Sin registro de usuarios: es un sistema de una sola persona."""
    valid_user = request.username == settings.MINDOS_ADMIN_USERNAME
    valid_password = verify_password(request.password, settings.MINDOS_ADMIN_PASSWORD_HASH)
    if not (valid_user and valid_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña incorrectos.")

    token = create_access_token(
        subject=request.username, secret=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM, expiry_minutes=settings.JWT_EXPIRY_MINUTES,
    )
    return LoginResponse(access_token=token, expires_in_minutes=settings.JWT_EXPIRY_MINUTES)


async def _read_body_capped(request: Request, max_bytes: int) -> bytes:
    """
    Lee el body en streaming y aborta apenas se supera `max_bytes`, sin llegar a bufferizar
    un body arbitrariamente grande en memoria (F3-T1: "rechaza lo malformado antes de rutear").
    Un `Content-Length` declarado de más también se rechaza antes de leer nada.
    """
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Cuerpo de la petición demasiado grande.")

    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > max_bytes:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Cuerpo de la petición demasiado grande.")
    return bytes(chunks)


@app.api_route("/api/v1/{service_key}/{rest_of_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(
    service_key: str,
    rest_of_path: str,
    request: Request,
    http_client: httpx.AsyncClient = Depends(get_http_client),
    _identity: str = Depends(require_auth),
):
    """
    Routing/proxy (F3-T1): `/api/v1/{memory|agents|comms|approvals}/...` reenviado sin
    transformar al servicio interno correspondiente. Ninguno de esos servicios se expone
    directamente — este es el único punto de entrada autenticado.
    """
    base_url = SERVICE_ROUTES.get(service_key)
    if not base_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Servicio desconocido: '{service_key}'.")

    body = await _read_body_capped(request, settings.MAX_BODY_BYTES)

    forward_headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP_HEADERS}
    forward_headers["X-Correlation-Id"] = str(get_correlation_id())

    downstream_url = f"{base_url.rstrip('/')}/api/v1/{service_key}/{rest_of_path}"
    try:
        downstream_resp = await http_client.request(
            request.method, downstream_url, params=request.query_params,
            content=body, headers=forward_headers,
        )
    except httpx.RequestError as e:
        logger.error("Servicio downstream inalcanzable", service=service_key, url=downstream_url, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"No se pudo contactar al servicio '{service_key}'."
        ) from e

    response_headers = {
        k: v for k, v in downstream_resp.headers.items() if k.lower() not in _HOP_BY_HOP_HEADERS
    }
    return Response(
        content=downstream_resp.content, status_code=downstream_resp.status_code,
        headers=response_headers, media_type=downstream_resp.headers.get("content-type"),
    )

# Fin del módulo main
