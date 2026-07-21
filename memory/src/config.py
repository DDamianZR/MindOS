from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "MemoryService"
    MINDOS_ENV: str = "development"

    # Configuración de Almacenamiento y Persistencia
    DATABASE_TYPE: str = "in_memory"  # 'postgres' o 'in_memory'
    DATABASE_URL: str = "postgresql+asyncpg://mindos_user:mindos_secure_password@localhost:5432/mindos_db"

    # Configuración de Ollama y Modelos
    OLLAMA_URL: str = "http://localhost:11434"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_DIM: int = 768  # nomic-embed-text = 768. Debe coincidir con Vector(dim) en models.py
    EMBEDDING_PROVIDER: str = "ollama"  # 'ollama' (real) | 'mock' (tests/dev sin Ollama)

    # Event Bus
    REDIS_URL: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
