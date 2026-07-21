import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from memory.src.config import settings
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding
from memory.src.infrastructure.database.repositories import PgDatabaseRepository
from memory.src.infrastructure.vector.pgvector import PgVectorStoreRepository

configure_logging("MemoryService", settings.MINDOS_ENV)
logger = get_logger("memory_main")

# Instanciar almacenes en memoria compartidos si DATABASE_TYPE es 'in_memory'
in_memory_db = InMemoryDatabase()
in_memory_vector_store = InMemoryVectorStore()
mock_embedding = MockEmbedding()

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
    repos=Depends(get_repositories)
):
    db_repo, vector_repo = repos
    # Generar UUIDv7 si es un nuevo nodo
    import uuid

    node_id = request.node_id or uuid.uuid4() # En prod/python3.12: uuid.uuid7()

    # 1. Guardar en Base de Datos Relacional
    await db_repo.save_node(node_id, request.entity_type)

    # Obtener última versión para calcular el número de la siguiente versión
    latest_ver = await db_repo.get_latest_node_version(node_id)
    next_version = (latest_ver["version"] + 1) if latest_ver else 1

    await db_repo.save_node_version(
        node_id=node_id,
        version=next_version,
        title=request.title,
        content=request.content,
        author=request.author,
        metadata=request.metadata,
        parent_version_id=latest_ver["node_id"] if latest_ver else None
    )

    # 2. Generar Embedding Vectorial y guardar en pgvector
    vector = await mock_embedding.embed_query(request.content)
    await vector_repo.upsert(
        vector_id=str(node_id),
        embedding=vector,
        payload={"title": request.title, "type": request.entity_type}
    )

    if settings.DATABASE_TYPE == "postgres":
        # Guardar en base de datos física
        await db_repo.session.commit()

    return IngestKnowledgeResponse(
        node_id=node_id,
        version=next_version,
        title=request.title,
        author=request.author,
        created_at=latest_ver["created_at"] if latest_ver else datetime.now(timezone.utc)
    )

@app.post("/api/v1/memory/search", response_model=SearchKnowledgeResponse)
async def search_knowledge(
    query: str,
    limit: int = 3,
    repos=Depends(get_repositories)
):
    db_repo, vector_repo = repos
    # Realizar búsqueda semántica e híbrida
    query_vector = await mock_embedding.embed_query(query)
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
