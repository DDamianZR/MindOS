import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, status
from mindos_common.context import set_correlation_id
from mindos_common.event_bus import RedisEventBus
from mindos_common.ids import new_id
from mindos_common.logging import configure_logging, get_logger
from mindos_schemas.api.v1.memory_dto import (
    GetNodeHistoryResponse,
    IngestKnowledgeRequest,
    IngestKnowledgeResponse,
    NodeVersionDto,
    SearchKnowledgeResponse,
    SearchResultItem,
)
from mindos_schemas.capabilities import Capability, RegisterCapabilitiesRequest
from mindos_schemas.events.v1.memory_events import (
    KnowledgeCreatedEventData,
    KnowledgeUpdatedEventData,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from memory.src.config import settings
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding
from memory.src.infrastructure.adapters.ollama_embedding import OllamaEmbedding
from memory.src.infrastructure.database.repositories import PgDatabaseRepository
from memory.src.infrastructure.vector.pgvector import PgVectorStoreRepository

configure_logging("MemoryService", settings.MINDOS_ENV)
logger = get_logger("memory_main")

# Instanciar almacenes en memoria compartidos si DATABASE_TYPE es 'in_memory'
in_memory_db = InMemoryDatabase()
in_memory_vector_store = InMemoryVectorStore()


def _make_embedding():
    """Selecciona el proveedor de embeddings segun configuracion (real Ollama o mock)."""
    if settings.EMBEDDING_PROVIDER == "ollama":
        logger.info("Embeddings via Ollama", model=settings.EMBEDDING_MODEL, dim=settings.EMBEDDING_DIM)
        return OllamaEmbedding(settings.OLLAMA_URL, settings.EMBEDDING_MODEL)
    logger.info("Embeddings via Mock (dim=%s)", settings.EMBEDDING_DIM)
    return MockEmbedding(settings.EMBEDDING_DIM)


embedding_provider = _make_embedding()

# Bus de eventos (Redis Streams). La construcción es perezosa: no conecta hasta publicar.
event_bus = RedisEventBus(settings.REDIS_URL)

# Stream canónico de eventos de memoria
MEMORY_STREAM = "mindos.memory"


async def publish_event(event_type: str, data, correlation_id) -> None:
    """
    Publica un evento en el bus de forma best-effort: si Redis no está disponible, se registra
    una advertencia pero NO se interrumpe la operación (el event_log en DB es el registro durable).
    """
    try:
        await event_bus.publish(MEMORY_STREAM, event_type, data, correlation_id)
    except Exception as e:  # noqa: BLE001 - degradación elegante ante Redis caído
        logger.warning("No se pudo publicar el evento en el bus", event_type=event_type, error=str(e))

# Configurar motor SQLAlchemy asíncrono para PostgreSQL
engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db_session():
    """Dependencia para inyectar la sesión relacional."""
    if settings.DATABASE_TYPE == "postgres":
        async with async_session_factory() as session:
            yield session
    else:
        yield None

async def get_repositories(session: AsyncSession = Depends(get_db_session)):
    """Inyecta los adaptadores correspondientes de base de datos y vectores."""
    if settings.DATABASE_TYPE == "postgres":
        db_repo = PgDatabaseRepository(session)
        vector_repo = PgVectorStoreRepository(session)
        return db_repo, vector_repo
    else:
        return in_memory_db, in_memory_vector_store

async def register_capabilities():
    """Registra de forma proactiva las capacidades del servicio de memoria en el agente Planner."""
    cap = Capability(
        name="search_knowledge",
        description="Busca en la base semántica y grafo de conocimiento de MindOS",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta de búsqueda"}
            },
            "required": ["query"]
        },
        provider_service="memory",
        endpoint_path="/api/v1/memory/search"
    )

    # URL de registro del servicio agents en el docker bridge network
    url = "http://agents:8002/api/v1/capabilities/register"
    # Fallback local para desarrollo fuera de docker
    fallback_url = "http://localhost:8002/api/v1/capabilities/register"

    payload = RegisterCapabilitiesRequest(capabilities=[cap])

    logger.info("Registrando capacidades de Memoria en el ecosistema...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        for target_url in [url, fallback_url]:
            try:
                response = await client.post(target_url, json=payload.model_dump())
                if response.status_code == 200:
                    logger.info("Capacidades registradas con éxito", url=target_url)
                    return
            except Exception:
                # Silenciar errores y reintentar con el fallback
                pass
        logger.warning("No se pudo contactar con el Registry de Agentes. Las capacidades se registrarán en diferido.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tareas de inicio
    if settings.DATABASE_TYPE == "postgres":
        logger.info("Conectando a base de datos PostgreSQL", url=settings.DATABASE_URL)
    else:
        logger.info("Iniciando Memory Service con almacenamiento In-Memory")

    # Lanzar registro de capacidades en segundo plano para no bloquear el arranque
    asyncio.create_task(register_capabilities())
    yield
    # Tareas de apagado
    await event_bus.close()
    if settings.DATABASE_TYPE == "postgres":
        await engine.dispose()
        logger.info("Conexiones de PostgreSQL liberadas.")

app = FastAPI(
    title="MindOS Memory Service",
    description="Motor de Conocimiento, RAG y Grafo relacional temporal de MindOS",
    version="1.0.0",
    lifespan=lifespan
)

@app.post(
    "/api/v1/memory/ingest",
    response_model=IngestKnowledgeResponse,
    status_code=status.HTTP_201_CREATED
)
async def ingest_knowledge(
    request: IngestKnowledgeRequest,
    repos=Depends(get_repositories),
    x_correlation_id: UUID | None = Header(default=None, alias="X-Correlation-Id")
):
    db_repo, vector_repo = repos
    # Propagar o generar el correlation_id para trazabilidad end-to-end
    correlation_id = x_correlation_id or new_id()
    set_correlation_id(correlation_id)

    # Generar UUIDv7 (ordenable temporalmente) si es un nuevo nodo
    node_id = request.node_id or new_id()

    # 1. Guardar en Base de Datos Relacional
    await db_repo.save_node(node_id, request.entity_type)

    # Obtener última versión para calcular el número de la siguiente versión
    latest_ver = await db_repo.get_latest_node_version(node_id)
    next_version = (latest_ver["version"] + 1) if latest_ver else 1

    # El padre de esta versión es la versión previa (su version_id), NO el node_id.
    parent_version_id = latest_ver["version_id"] if latest_ver else None
    version_id = new_id()

    await db_repo.save_node_version(
        node_id=node_id,
        version_id=version_id,
        version=next_version,
        title=request.title,
        content=request.content,
        author=request.author,
        metadata=request.metadata,
        parent_version_id=parent_version_id
    )

    # 2. Generar Embedding Vectorial y guardar en pgvector
    vector = await embedding_provider.embed_query(request.content)
    await vector_repo.upsert(
        vector_id=str(node_id),
        embedding=vector,
        payload={"title": request.title, "type": request.entity_type}
    )

    # 3. Construir el evento de dominio (created si es v1, updated en adelante)
    if next_version == 1:
        event_type = "com.mindos.memory.knowledge.created"
        event_data = KnowledgeCreatedEventData(
            node_id=node_id, entity_type=request.entity_type,
            version=next_version, title=request.title, author=request.author,
        )
    else:
        event_type = "com.mindos.memory.knowledge.updated"
        event_data = KnowledgeUpdatedEventData(
            node_id=node_id, version=next_version, title=request.title,
            author=request.author, parent_version_id=parent_version_id,
        )

    # 4. Registro durable en el event_log (dentro de la misma transacción que el conocimiento)
    await db_repo.save_event_log(new_id(), event_type, event_data.model_dump(mode="json"))

    if settings.DATABASE_TYPE == "postgres":
        # Guardar en base de datos física (conocimiento + event_log atómicos)
        await db_repo.session.commit()

    # 5. Notificar al ecosistema por el bus (best-effort, tras la persistencia durable)
    await publish_event(event_type, event_data, correlation_id)

    # Releer la versión recién creada para devolver su timestamp real de persistencia
    saved_ver = await db_repo.get_latest_node_version(node_id)
    created_at = saved_ver["created_at"] if saved_ver else datetime.now(timezone.utc)

    return IngestKnowledgeResponse(
        node_id=node_id,
        version=next_version,
        title=request.title,
        author=request.author,
        created_at=created_at
    )

@app.post("/api/v1/memory/search", response_model=SearchKnowledgeResponse)
async def search_knowledge(
    query: str,
    limit: int = 3,
    repos=Depends(get_repositories)
):
    db_repo, vector_repo = repos
    # Realizar búsqueda semántica e híbrida
    query_vector = await embedding_provider.embed_query(query)
    vector_results = await vector_repo.search(query_vector, limit=limit)

    results = []
    for res in vector_results:
        from uuid import UUID
        nid = UUID(res.id)
        ver = await db_repo.get_latest_node_version(nid)
        if ver:
            results.append(SearchResultItem(
                node_id=nid,
                version=ver["version"],
                title=ver["title"],
                content=ver["content"],
                score=res.score,
                metadata=ver["metadata"]
            ))

    return SearchKnowledgeResponse(query=query, results=results)

@app.get("/api/v1/memory/node/{node_id}/history", response_model=GetNodeHistoryResponse)
async def get_node_history(
    node_id: UUID,
    repos=Depends(get_repositories)
):
    db_repo, _ = repos

    # Buscar el nodo para validar tipo
    ver_list = await db_repo.get_node_versions(node_id)
    if not ver_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nodo {node_id} no encontrado en memoria."
        )

    versions_dto = [
        NodeVersionDto(
            version=v["version"],
            title=v["title"],
            content=v["content"],
            author=v["author"],
            created_at=v["created_at"],
            parent_version_id=v["parent_version_id"]
        ) for v in ver_list
    ]

    # Encontrar el tipo en la primera versión
    latest = ver_list[-1]

    return GetNodeHistoryResponse(
        node_id=node_id,
        entity_type=latest["metadata"].get("type", "note"),
        versions=versions_dto
    )

# Fin del módulo main
