from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "MCPService"
    MINDOS_ENV: str = "development"

    # F4-T2: el servidor MCP habla SIEMPRE con MindOS a través del Gateway (único punto de
    # entrada, F3-T1) — sea que corra dentro del stack Docker o como proceso stdio en la
    # máquina del usuario apuntando a una instancia remota de MindOS.
    GATEWAY_URL: str = "http://localhost:8000"
    MINDOS_API_KEY: str = ""

    # Transporte HTTP (remoto, detrás del Gateway): puerto propio + su propia API key. Defensa
    # en profundidad — el Gateway ya autentica al proxyar, pero un acceso directo también debe
    # estarlo, igual que cualquier otro servicio interno no debería confiar solo en el perímetro.
    MCP_HTTP_PORT: int = 8005
    MCP_API_KEY: str = "change-me-in-env"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # El .env de la raíz es compartido por todos los servicios: cada uno ignora las
        # variables de los demás (p.ej. ANTHROPIC_API_KEY) en vez de negarse a arrancar.
        extra = "ignore"


settings = Settings()
