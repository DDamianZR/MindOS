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

    # --- Proveedor de razonamiento (F7-T1) ---
    # 'auto': Claude si hay ANTHROPIC_API_KEY; si no, Ollama en producción y Mock en desarrollo
    # (el comportamiento previo a la Fase 7). 'anthropic' | 'ollama' | 'mock' lo fijan explícito.
    LLM_PROVIDER: str = "auto"
    # Vacío = el SDK resuelve la credencial por su cuenta (variable de entorno, perfil de
    # `ant auth login`...). Nunca se escribe en el repo: vive en `.env`.
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-5-5"
    # Esfuerzo de razonamiento del planner/reviewer (LlmPort): tareas agénticas de varios pasos.
    ANTHROPIC_EFFORT: str = "medium"
    # Fallback del lado del servidor cuando un clasificador de seguridad declina una petición
    # (beta `server-side-fallback-2026-07-01`). Sin él, una petición declinada simplemente termina.
    ANTHROPIC_FALLBACKS: bool = True

    # --- Asistente personal (F7-T2..T4) ---
    # Esfuerzo del chat: 'low' es el punto de partida recomendado para conversación y búsqueda
    # (responde antes); súbelo a 'medium' si las respuestas se quedan cortas de análisis.
    ASSISTANT_EFFORT: str = "low"
    ASSISTANT_MAX_TOKENS: int = 16000
    # Tope de rondas de herramientas por turno: corta un bucle que no converge.
    ASSISTANT_MAX_TOOL_ROUNDS: int = 10
    # Nombre de la persona dueña de esta instancia (mono-usuario). Opcional.
    MINDOS_OWNER_NAME: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
