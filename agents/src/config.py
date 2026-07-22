from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "AgentsService"
    MINDOS_ENV: str = "development"

    # Configuración de Servidor
    PORT: int = 8002

    # URLs de Servicios Periféricos
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3:8b"
    MEMORY_URL: str = "http://memory:8001"
    # F3-T7: a dónde notificar (aprobaciones pendientes, respuesta final) cuando el goal vino
    # de un mensaje con canal de origen (`reply_to`).
    COMMS_URL: str = "http://comms:8003"

    # Event Bus
    REDIS_URL: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
