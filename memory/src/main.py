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
    ArchiveNodeResponse,
    ContextBundle,
    ContextRequest,
    CreateRelationRequest,
    CreateRelationResponse,
    GetNodeHistoryResponse,
    GetNodeNeighborsResponse,
    GetNodeProvenanceResponse,
    IngestKnowledgeRequest,
    IngestKnowledgeResponse,
    NeighborEdgeDto,
    NodeVersionDto,
    SearchKnowledgeResponse,
    SearchResultItem,
    SourceDto,
    TimeTravelRelationDto,
    TimeTravelResponse,
    VersionProvenanceDto,
)
from mindos_schemas.capabilities import Capability, RegisterCapabilitiesRequest
from mindos_schemas.domain import RelationType
from mindos_schemas.events.v1.memory_events import (
    KnowledgeArchivedEventData,
    KnowledgeCreatedEventData,
    KnowledgeUpdatedEventData,
    RelationCreatedEventData,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from memory.src.application.services.context_builder import ContextBuilderService
from memory.src.config import settings
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_thinking_graph import InMemoryThinkingGraph
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding
from memory.src.infrastructure.adapters.ollama_embedding import OllamaEmbedding
from memory.src.infrastructure.database.repositories import PgDatabaseRepository
from memory.src.infrastructure.database.thinking_graph_repository import PgThinkingGraphRepository
from memory.src.infrastructure.vector.pgvector import PgVectorStoreRepository

configure_logging("MemoryService", settings.MINDOS_ENV)
logger = get_logger("memory_main")

# Instanciar almacenes en memoria compartidos si DATABASE_TYPE es 'in_memory'
in_memory_db = InMemoryDatabase()
in_memory_vector_store = InMemoryVectorStore()
in_memory_thinking_graph = InMemoryThinkingGraph()


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

async def get_thinking_graph_repo(session: AsyncSession = Depends(get_db_session)):
    """Inyecta el adaptador del Thinking Graph (F2-T1)."""
    if settings.DATABASE_TYPE == "postgres":
        return PgThinkingGraphRepository(session)
    return in_memory_thinking_graph

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

@app.get("/health")
async def health():
    """Liveness básico para healthchecks de Docker/Traefik."""
    return {"status": "ok", "service": "memory", "database": settings.DATABASE_TYPE}


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

    # Generar el embedding una única vez: se reutiliza para el dedup semántico y el upsert final.
    vector = await embedding_provider.embed_query(request.content)

    # Dedup semántico (F1-T5): solo para capturas nuevas (sin node_id explícito) y si el caller
    # no fuerza on_duplicate="force_new". Busca el vecino más cercano y, si supera el umbral de
    # similitud Y ese nodo sigue activo (no archivado), lo trata como casi-duplicado.
    duplicate_of: UUID | None = None
    duplicate_score: float | None = None
    if request.node_id is None and request.on_duplicate != "force_new":
        candidates = await vector_repo.search(vector, limit=1)
        if candidates and candidates[0].score >= settings.DEDUP_SIMILARITY_THRESHOLD:
            candidate_id = UUID(candidates[0].id)
            candidate_ver = await db_repo.get_latest_node_version(candidate_id, include_archived=False)
            if candidate_ver:
                duplicate_of = candidate_id
                duplicate_score = candidates[0].score

    # Generar UUIDv7 (ordenable temporalmente) si es un nodo nuevo; reutilizar el node_id
    # provisto explícitamente, o el del duplicado detectado si on_duplicate="new_version".
    if request.node_id is not None:
        node_id = request.node_id
    elif duplicate_of is not None and request.on_duplicate == "new_version":
        node_id = duplicate_of
    else:
        node_id = new_id()

    # 1. Guardar en Base de Datos Relacional
    await db_repo.save_node(node_id, request.object_type.value)

    # Obtener última versión para calcular el número de la siguiente versión
    latest_ver = await db_repo.get_latest_node_version(node_id)
    next_version = (latest_ver["version"] + 1) if latest_ver else 1

    # El padre de esta versión es la versión previa (su version_id), NO el node_id.
    parent_version_id = latest_ver["version_id"] if latest_ver else None
    version_id = new_id()

    # Resolver el origen (provenance): reutilizar una fuente existente por (kind, uri) o crear una nueva.
    provenance_source_id = None
    if request.source is not None:
        existing_source = None
        if request.source.uri:
            existing_source = await db_repo.find_source_by_kind_uri(request.source.kind.value, request.source.uri)
        if existing_source:
            provenance_source_id = existing_source["id"]
        else:
            provenance_source_id = new_id()
            await db_repo.save_source(
                source_id=provenance_source_id,
                kind=request.source.kind.value,
                uri=request.source.uri,
                raw_ref=request.source.raw_ref,
                metadata=request.source.metadata,
            )

    await db_repo.save_node_version(
        node_id=node_id,
        version_id=version_id,
        version=next_version,
        title=request.title,
        content=request.content,
        author=request.author,
        metadata=request.metadata,
        parent_version_id=parent_version_id,
        confidence=request.confidence,
        importance=request.importance,
        status=request.status.value,
        evidence=[e.model_dump(mode="json") for e in request.evidence],
        provenance_source_id=provenance_source_id,
    )

    # 2. Guardar el embedding (ya calculado arriba, reutilizado del chequeo de dedup)
    await vector_repo.upsert(
        vector_id=str(node_id),
        embedding=vector,
        payload={"title": request.title, "type": request.object_type.value}
    )

    # 3. Construir el evento de dominio (created si es v1, updated en adelante)
    if next_version == 1:
        event_type = "com.mindos.memory.knowledge.created"
        event_data = KnowledgeCreatedEventData(
            node_id=node_id, object_type=request.object_type,
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

    # 5. Dedup semántico en modo "link" (F1-T5, default): el nodo nuevo queda enlazado al
    # casi-duplicado detectado, en vez de quedar aislado. "new_version" no crea relación porque
    # ya reutilizó el mismo node_id (no hay un segundo nodo que enlazar).
    dup_event_type = None
    dup_event_data = None
    if duplicate_of is not None and request.on_duplicate == "link":
        dup_metadata = {"similarity": duplicate_score}
        await db_repo.save_relation(
            source_id=node_id, target_id=duplicate_of,
            relation_type=RelationType.DUPLICATE_OF.value, metadata=dup_metadata,
        )
        dup_event_type = "com.mindos.memory.relation.created"
        dup_event_data = RelationCreatedEventData(
            source_id=node_id, target_id=duplicate_of,
            relation_type=RelationType.DUPLICATE_OF.value, metadata=dup_metadata,
        )
        await db_repo.save_event_log(new_id(), dup_event_type, dup_event_data.model_dump(mode="json"))

    if settings.DATABASE_TYPE == "postgres":
        # Guardar en base de datos física (conocimiento + relación de dedup + event_log atómicos)
        await db_repo.session.commit()

    # 6. Notificar al ecosistema por el bus (best-effort, tras la persistencia durable)
    await publish_event(event_type, event_data, correlation_id)
    if dup_event_type is not None:
        await publish_event(dup_event_type, dup_event_data, correlation_id)

    # Releer la versión recién creada para devolver su timestamp real de persistencia
    saved_ver = await db_repo.get_latest_node_version(node_id)
    created_at = saved_ver["created_at"] if saved_ver else datetime.now(timezone.utc)

    return IngestKnowledgeResponse(
        node_id=node_id,
        version=next_version,
        title=request.title,
        author=request.author,
        created_at=created_at,
        object_type=request.object_type,
        confidence=request.confidence,
        importance=request.importance,
        status=request.status,
        duplicate_of=duplicate_of,
        duplicate_score=duplicate_score,
    )


async def _set_node_tombstone(
    node_id: UUID, tombstoned: bool, repos, x_correlation_id: UUID | None
) -> ArchiveNodeResponse:
    """Lógica compartida de archivar/restaurar (F1-T4): nunca borra, solo marca `tombstoned_at`."""
    db_repo, _ = repos
    correlation_id = x_correlation_id or new_id()
    set_correlation_id(correlation_id)

    changed = await db_repo.set_latest_version_tombstone(node_id, tombstoned=tombstoned)
    if not changed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nodo {node_id} no encontrado en memoria."
        )

    event_type = "com.mindos.memory.knowledge.archived" if tombstoned else "com.mindos.memory.knowledge.restored"
    event_data = KnowledgeArchivedEventData(node_id=node_id)
    await db_repo.save_event_log(new_id(), event_type, event_data.model_dump(mode="json"))

    if settings.DATABASE_TYPE == "postgres":
        await db_repo.session.commit()

    await publish_event(event_type, event_data, correlation_id)
    return ArchiveNodeResponse(node_id=node_id, archived=tombstoned)


@app.post("/api/v1/memory/node/{node_id}/archive", response_model=ArchiveNodeResponse)
async def archive_node(
    node_id: UUID,
    repos=Depends(get_repositories),
    x_correlation_id: UUID | None = Header(default=None, alias="X-Correlation-Id")
):
    """
    Archiva un nodo (soft-delete, F1-T4): oculta su versión vigente de búsquedas y lecturas
    por defecto. Nunca borra físicamente — usar `include_archived=true` para recuperarlo,
    o `POST .../restore` para reactivarlo.
    """
    return await _set_node_tombstone(node_id, tombstoned=True, repos=repos, x_correlation_id=x_correlation_id)


@app.post("/api/v1/memory/node/{node_id}/restore", response_model=ArchiveNodeResponse)
async def restore_node(
    node_id: UUID,
    repos=Depends(get_repositories),
    x_correlation_id: UUID | None = Header(default=None, alias="X-Correlation-Id")
):
    """Restaura un nodo previamente archivado (F1-T4): vuelve a ser visible por defecto."""
    return await _set_node_tombstone(node_id, tombstoned=False, repos=repos, x_correlation_id=x_correlation_id)


# El almacén vectorial no conoce el concepto de "archivado" (F1-T4): puede devolver candidatos
# que luego resulten tombstoneados en la DB. Se pide más candidatos de los necesarios para
# compensar el filtrado posterior sin tener que repetir la búsqueda vectorial.
_SEARCH_OVERFETCH_FACTOR = 4
_SEARCH_OVERFETCH_MAX = 50


@app.post("/api/v1/memory/search", response_model=SearchKnowledgeResponse)
async def search_knowledge(
    query: str,
    limit: int = 3,
    include_archived: bool = False,
    repos=Depends(get_repositories)
):
    db_repo, vector_repo = repos
    # Realizar búsqueda semántica e híbrida
    query_vector = await embedding_provider.embed_query(query)
    fetch_limit = min(limit * _SEARCH_OVERFETCH_FACTOR, _SEARCH_OVERFETCH_MAX)
    vector_results = await vector_repo.search(query_vector, limit=fetch_limit)

    results = []
    for res in vector_results:
        if len(results) >= limit:
            break
        nid = UUID(res.id)
        ver = await db_repo.get_latest_node_version(nid, include_archived=include_archived)
        if ver:
            results.append(SearchResultItem(
                node_id=nid,
                version=ver["version"],
                title=ver["title"],
                content=ver["content"],
                score=res.score,
                metadata=ver["metadata"],
                object_type=ver.get("object_type"),
                confidence=ver.get("confidence", 0.5),
                importance=ver.get("importance", 0.5),
                status=ver.get("status", "active"),
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
            parent_version_id=v["parent_version_id"],
            confidence=v.get("confidence", 0.5),
            importance=v.get("importance", 0.5),
            status=v.get("status", "active"),
            evidence=v.get("evidence") or [],
            salience=v.get("salience", 0.5),
            tombstoned_at=v.get("tombstoned_at"),
        ) for v in ver_list
    ]

    # El tipo de objeto vive en el nodo padre; toda versión lo trae anexado por el repositorio.
    latest = ver_list[-1]

    return GetNodeHistoryResponse(
        node_id=node_id,
        object_type=latest.get("object_type", "note"),
        versions=versions_dto
    )

@app.get("/api/v1/memory/node/{node_id}/provenance", response_model=GetNodeProvenanceResponse)
async def get_node_provenance(
    node_id: UUID,
    repos=Depends(get_repositories)
):
    """
    Trazabilidad de origen (F1-T2): "¿de dónde vino este conocimiento?".
    Devuelve la cadena cronológica de versiones del nodo junto con la fuente (whatsapp, pdf,
    cli, ...) de la que provino cada una, cuando se conoce.
    """
    db_repo, _ = repos

    ver_list = await db_repo.get_node_versions(node_id)
    if not ver_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nodo {node_id} no encontrado en memoria."
        )

    chain = []
    for v in ver_list:
        source_dto = None
        source_id = v.get("provenance_source_id")
        if source_id:
            src = await db_repo.get_source(source_id)
            if src:
                source_dto = SourceDto(
                    id=src["id"], kind=src["kind"], uri=src["uri"],
                    raw_ref=src["raw_ref"], captured_at=src["captured_at"], metadata=src["metadata"],
                )
        chain.append(VersionProvenanceDto(
            version=v["version"], created_at=v["created_at"], author=v["author"], source=source_dto
        ))

    return GetNodeProvenanceResponse(node_id=node_id, chain=chain)

@app.get("/api/v1/memory/timetravel", response_model=TimeTravelResponse)
async def time_travel(
    node_id: UUID,
    at: datetime,
    max_depth: int = 1,
    repos=Depends(get_repositories)
):
    """
    Consulta temporal "as-of" (F1-T3): reconstruye el estado del nodo (versión + relaciones
    vigentes) tal como era en el instante `at`. Responde "¿qué pensaba sobre esto en esa fecha?".
    """
    db_repo, _ = repos

    ver = await db_repo.get_node_version_asof(node_id, at)
    if not ver:
        return TimeTravelResponse(node_id=node_id, at=at, found=False)

    relations = await db_repo.query_relations_asof(node_id, at, max_depth)
    relation_dtos = [
        TimeTravelRelationDto(
            source_id=r["source_id"], target_id=r["target_id"], relation_type=r["relation_type"]
        ) for r in relations
    ]

    version_dto = NodeVersionDto(
        version=ver["version"], title=ver["title"], content=ver["content"], author=ver["author"],
        created_at=ver["created_at"], parent_version_id=ver["parent_version_id"],
        confidence=ver.get("confidence", 0.5), importance=ver.get("importance", 0.5),
        status=ver.get("status", "active"), evidence=ver.get("evidence") or [],
        salience=ver.get("salience", 0.5), tombstoned_at=ver.get("tombstoned_at"),
    )

    return TimeTravelResponse(node_id=node_id, at=at, found=True, version=version_dto, relations=relation_dtos)


def _normalize_relation_type(relation_type: str, metadata: dict) -> tuple[str, dict, str | None]:
    """
    F1-T6: valida `relation_type` contra el catálogo `RelationType`. Si no pertenece, se
    normaliza a `CUSTOM` y el valor original se preserva en metadata — el grafo sigue siendo
    consultable/agrupable por un conjunto cerrado de tipos, sin bloquear etiquetas ad-hoc.
    Devuelve (relation_type_normalizado, metadata_resultante, custom_relation_type_o_None).
    """
    valid_values = {rt.value for rt in RelationType}
    if relation_type in valid_values:
        return relation_type, metadata, None
    normalized_metadata = {**metadata, "custom_relation_type": relation_type}
    return RelationType.CUSTOM.value, normalized_metadata, relation_type


@app.post("/api/v1/memory/relation", response_model=CreateRelationResponse)
async def create_relation(
    request: CreateRelationRequest,
    repos=Depends(get_repositories),
    x_correlation_id: UUID | None = Header(default=None, alias="X-Correlation-Id")
):
    """Crea una relación tipada entre dos Objetos Cognitivos del Knowledge Graph (F1-T6)."""
    db_repo, _ = repos
    correlation_id = x_correlation_id or new_id()
    set_correlation_id(correlation_id)

    relation_type, metadata, custom_type = _normalize_relation_type(request.relation_type, request.metadata)

    await db_repo.save_relation(
        source_id=request.source_id, target_id=request.target_id,
        relation_type=relation_type, metadata=metadata,
    )

    event_data = RelationCreatedEventData(
        source_id=request.source_id, target_id=request.target_id,
        relation_type=relation_type, metadata=metadata,
    )
    await db_repo.save_event_log(new_id(), "com.mindos.memory.relation.created", event_data.model_dump(mode="json"))

    if settings.DATABASE_TYPE == "postgres":
        await db_repo.session.commit()

    await publish_event("com.mindos.memory.relation.created", event_data, correlation_id)

    return CreateRelationResponse(
        source_id=request.source_id, target_id=request.target_id,
        relation_type=relation_type, custom_relation_type=custom_type,
    )


@app.get("/api/v1/memory/node/{node_id}/neighbors", response_model=GetNodeNeighborsResponse)
async def get_node_neighbors(
    node_id: UUID,
    depth: int = 2,
    repos=Depends(get_repositories)
):
    """Vecinos del Knowledge Graph alcanzables desde el nodo, hasta `depth` saltos (F1-T6)."""
    db_repo, _ = repos
    relations = await db_repo.query_relations_recursive(node_id, max_depth=depth)
    neighbors = [
        NeighborEdgeDto(
            source_id=r["source_id"], target_id=r["target_id"],
            relation_type=r["relation_type"], metadata=r.get("metadata") or {},
        ) for r in relations
    ]
    return GetNodeNeighborsResponse(node_id=node_id, depth=depth, neighbors=neighbors)


@app.post("/api/v1/memory/context", response_model=ContextBundle)
async def get_context(
    request: ContextRequest,
    repos=Depends(get_repositories)
):
    """
    Context Builder v2 / GraphRAG (F1-T7): contexto estructurado y citable para agentes.
    Combina similitud vectorial + expansión por grafo + reranking por importancia/recencia/
    confianza. Usado por el servicio de Agents en vez de construir el prompt a mano.
    """
    db_repo, vector_repo = repos
    context_builder = ContextBuilderService(
        vector_store=vector_repo,
        database=db_repo,
        embedding=embedding_provider,
        weight_similarity=settings.CONTEXT_WEIGHT_SIMILARITY,
        weight_importance=settings.CONTEXT_WEIGHT_IMPORTANCE,
        weight_recency=settings.CONTEXT_WEIGHT_RECENCY,
        weight_confidence=settings.CONTEXT_WEIGHT_CONFIDENCE,
        recency_halflife_days=settings.CONTEXT_RECENCY_HALFLIFE_DAYS,
        graph_expansion_decay=settings.CONTEXT_GRAPH_EXPANSION_DECAY,
    )
    return await context_builder.build_context(request.query, limit=request.limit, depth=request.depth)


# Routers de Fase 2 (Thinking Graph, F2-T1+). Se importan al final para evitar ciclos: estos
# routers importan `get_thinking_graph_repo` desde este mismo módulo.
from memory.src.api.thinking_router import router as thinking_router  # noqa: E402

app.include_router(thinking_router)

# Fin del módulo main
