from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "GatewayService"
    MINDOS_ENV: str = "development"

    # Enrutamiento a servicios downstream (F3-T1): nunca expuestos directamente, solo vía Gateway.
    MEMORY_URL: str = "http://localhost:8001"
    AGENTS_URL: str = "http://localhost:8002"
    COMMS_URL: str = "http://localhost:8003"
    MCP_URL: str = "http://localhost:8005"

    # F4-T1: el Dashboard corre en su propio origen y llama al Gateway directo desde el
    # navegador — sin CORS, el navegador bloquea la respuesta aunque la petición esté
    # correctamente autenticada. Un solo origen explícito (no "*"): no hace falta más para un
    # sistema mono-usuario, y evita abrir el Gateway a cualquier origen arbitrario.
    DASHBOARD_URL: str = "http://localhost:3000"

    # Event Bus (rate-limit usa Redis directamente, no CloudEvents)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth mono-usuario (F3-T1): API key para servicios, JWT para el humano.
    # El hash Argon2 se genera con `python -m gateway.scripts.hash_password` y vive en .env, nunca
    # la contraseña en texto plano.
    MINDOS_API_KEY: str = "change-me-in-env"
    MINDOS_ADMIN_USERNAME: str = "admin"
    MINDOS_ADMIN_PASSWORD_HASH: str = ""
    JWT_SECRET: str = "change-me-in-env"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 1440  # 24h — mono-usuario, sesión larga, sin refresh token en v1

    # Rate limit (F3-T1): ventana fija por IP, sencillo y suficiente para un sistema mono-usuario.
    RATE_LIMITER_TYPE: str = "in_memory"  # 'redis' (producción) | 'in_memory' (tests/dev sin Redis)
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Validación de payloads (F3-T1): límite de tamaño antes de rutear (protege downstream).
    MAX_BODY_BYTES: int = 10 * 1024 * 1024  # 10 MiB

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # El .env de la raíz es compartido por todos los servicios: cada uno ignora las
        # variables de los demás (p.ej. ANTHROPIC_API_KEY) en vez de negarse a arrancar.
        extra = "ignore"


settings = Settings()

# Mapa de enrutamiento: prefijo del path (/api/v1/{clave}/...) -> URL base del servicio.
# "approvals", "thinking" y "cognitive" no son servicios propios: viven como routers montados
# en Agents/Memory (ver approvals_router.py, thinking_router.py, cognitive_router.py) bajo su
# propio prefijo /api/v1/{router}/... -- el proxy reconstruye la URL downstream como
# "{base_url}/api/v1/{service_key}/{resto}", así que cada uno necesita su propia entrada aquí
# para que esa reconstrucción caiga exactamente en la ruta real del router, aunque no sea "su"
# servicio dueño. Sin esto el Gateway responde 404 "Servicio desconocido" (F4-T1: se detectó al
# conectar el Visor de razonamiento y el Panel de las 7 preguntas del Dashboard).
SERVICE_ROUTES = {
    "memory": settings.MEMORY_URL,
    "agents": settings.AGENTS_URL,
    "comms": settings.COMMS_URL,
    "approvals": settings.AGENTS_URL,
    "thinking": settings.MEMORY_URL,
    "cognitive": settings.MEMORY_URL,
    "mcp": settings.MCP_URL,
}
