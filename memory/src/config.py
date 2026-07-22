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

    # Pipeline de ingestión (F3-T5): a dónde disparar un agente si el mensaje es una pregunta.
    AGENTS_URL: str = "http://localhost:8002"
    # Auto-enlazado (F3-T5 paso 4): mismo calibre que CONTRADICTION_SIMILARITY_THRESHOLD (F2-T5).
    AUTO_LINK_SIMILARITY_THRESHOLD: float = 0.65

    # Dedup semántico en ingest (F1-T5)
    DEDUP_SIMILARITY_THRESHOLD: float = 0.92

    # Context Builder v2 / GraphRAG (F1-T7): pesos del reranking (deben sumar ~1.0, no se valida)
    CONTEXT_WEIGHT_SIMILARITY: float = 0.5
    CONTEXT_WEIGHT_IMPORTANCE: float = 0.2
    CONTEXT_WEIGHT_RECENCY: float = 0.15
    CONTEXT_WEIGHT_CONFIDENCE: float = 0.15
    CONTEXT_RECENCY_HALFLIFE_DAYS: float = 30.0  # recencia=0.5 a esta antigüedad; decae exponencialmente
    CONTEXT_GRAPH_EXPANSION_DECAY: float = 0.7  # descuento de similitud heredada para nodos hallados por grafo

    # LLM para razonamiento (F2-T5: detección de contradicciones)
    LLM_PROVIDER: str = "ollama"  # 'ollama' (real) | 'mock' (tests/dev sin Ollama)
    LLM_MODEL_REASONING: str = "qwen3:8b"

    # Detección de contradicciones (F2-T5)
    # Umbral MÍNIMO de similitud para siquiera preguntarle al LLM (filtra candidatos irrelevantes,
    # calibrado empíricamente: pares no relacionados ~0.5, mismo tema con/sin contradicción ~0.77-0.90).
    CONTRADICTION_SIMILARITY_THRESHOLD: float = 0.65
    CONTRADICTION_TOP_K: int = 5

    # OCR (F3-T6): imágenes/PDFs escaneados capturados por el pipeline de ingestión (F3-T5)
    OCR_PROVIDER: str = "tesseract"  # 'tesseract' (real) | 'mock' (tests/dev sin el binario)
    OCR_LANGUAGES: str = "spa+eng"

    # STT (F3-T6): notas de voz capturadas por el pipeline de ingestión (F3-T5)
    STT_PROVIDER: str = "faster_whisper"  # 'faster_whisper' (real) | 'mock' (tests/dev)
    STT_MODEL_SIZE: str = "small"

    # Storage (F3-T6): blobs originales (PDFs, imágenes, audio) referenciados por `source`.
    # Default 'in_memory' (como DATABASE_TYPE): 'local_fs' escribe al disco en __init__, así
    # que un default distinto de in_memory crearía directorios fuera del repo en cada import
    # de main.py durante tests/dev local. Producción lo fija explícito vía compose.
    STORAGE_TYPE: str = "in_memory"  # 'local_fs' | 'minio' | 'in_memory'
    STORAGE_LOCAL_DIR: str = "/data/storage"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "mindos"
    MINIO_SECURE: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
