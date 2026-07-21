import asyncio
from uuid import UUID

from mindos_common.context import set_correlation_id

# Iniciar logging estructurado básico para la simulación
from mindos_common.logging import configure_logging, get_logger

# Importar contratos
from mindos_schemas.capabilities import Capability

from agents.src.domain.executor.capability_executor import CapabilityExecutor
from agents.src.domain.planner.llm_planner import LlmPlanner
from agents.src.domain.planner.llm_reviewer import LlmReviewer

# Importar componentes de Agents
from agents.src.infrastructure.adapters.in_memory_capability_registry import (
    InMemoryCapabilityRegistry,
)
from agents.src.infrastructure.adapters.mock_llm import MockLlm as AgentsMockLlm
from memory.src.application.services.context_builder import ContextBuilderService

# Importar componentes de Memory
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding

configure_logging("SimulationTest", "INFO")
logger = get_logger("simulation")

async def run_simulation():
    # Establecer un ID de correlación global para el flujo de la simulación
    sim_correlation_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414902")
    set_correlation_id(sim_correlation_id)

    logger.info("Iniciando Simulación del Kernel de MindOS (Fase 2)", correlation_id=sim_correlation_id)

    # 1. Inicializar infraestructura In-Memory de Memory Service
    db = InMemoryDatabase()
    vector_store = InMemoryVectorStore()
    embedding_engine = MockEmbedding()

    context_builder = ContextBuilderService(vector_store, db, embedding_engine)

    # 2. Ingestar conocimiento de prueba en la Memoria
    # Nodo 1: Nota de Configuración de Traefik (UUIDv7 simulado)
    node_traefik_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414900")
    await db.save_node(node_traefik_id, "note")
    await db.save_node_version(
        node_id=node_traefik_id,
        version=1,
        title="Configuración Traefik SSL",
        content="Traefik está configurado como API Gateway escuchando en el puerto 443 con certificados SSL automáticos de Let's Encrypt.",
        author="user",
        metadata={"tags": ["infra", "ssl"]}
    )
    # Calcular e indexar vector de Traefik
    traefik_vector = await embedding_engine.embed_query("Configuración Traefik SSL puerto 443")
    await vector_store.upsert(
        vector_id=str(node_traefik_id),
        embedding=traefik_vector,
        payload={"title": "Configuración Traefik SSL", "type": "note"}
    )

    # Nodo 2: Documento de Docker Compose (UUIDv7 simulado)
    node_docker_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414901")
    await db.save_node(node_docker_id, "document")
    await db.save_node_version(
        node_id=node_docker_id,
        version=1,
        title="Docker Compose Producción",
        content="docker-compose.yml define los servicios de memory, agents y el gateway de Traefik montando el volumen storage/.",
        author="user",
        metadata={"format": "yaml"}
    )
    # Calcular e indexar vector de Docker
    docker_vector = await embedding_engine.embed_query("docker-compose.yml define servicios gateway Traefik")
    await vector_store.upsert(
        vector_id=str(node_docker_id),
        embedding=docker_vector,
        payload={"title": "Docker Compose Producción", "type": "document"}
    )

    # Enlazar los nodos en el Grafo de Conocimiento
    # Traefik -> BELONGS_TO -> Docker Compose
    await db.save_relation(
        source_id=node_traefik_id,
        target_id=node_docker_id,
        relation_type="BELONGS_TO",
        metadata={"created_by": "user"}
    )

    logger.info("Memoria inicializada con nodos y relaciones en el grafo")

    # 3. Inicializar e inscribir capacidades en el Registro
    registry = InMemoryCapabilityRegistry()

    search_cap = Capability(
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

    send_cap = Capability(
        name="send_chat_message",
        description="Envía un mensaje de chat al usuario",
        parameters_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Mensaje a enviar"}
            },
            "required": ["message"]
        },
        provider_service="communication",
        endpoint_path="/api/v1/communication/send"
    )

    await registry.register([search_cap, send_cap])
    logger.info("Capacidades 'search_knowledge' y 'send_chat_message' registradas en el CapabilityRegistry")

    # 4. Inicializar agentes
    agents_llm = AgentsMockLlm()
    planner = LlmPlanner(agents_llm)
    reviewer = LlmReviewer(agents_llm)
    executor = CapabilityExecutor(registry)

    # Registrar el manejador de la capacidad de búsqueda para que el Executor llame a la memoria real en memoria
    async def mock_search_handler(inputs):
        query = inputs.get("query", "")
        # Llamar al ContextBuilder real
        return await context_builder.build_context(query)

    async def mock_send_handler(inputs):
        msg = inputs.get("message", "")
        return f"[Simulación Communication] Mensaje enviado al usuario con éxito: '{msg}'"

    executor.register_mock_handler("search_knowledge", mock_search_handler)
    executor.register_mock_handler("send_chat_message", mock_send_handler)

    # 5. Ejecutar flujo completo de planificación y revisión (MVP)
    goal = "Revisar configuración de Traefik y encontrar su puerto."
    logger.info(f"Usuario solicita meta: '{goal}'")

    # 5a. Obtener contexto previo
    initial_context = await context_builder.build_context("Traefik")
    logger.info("ContextBuilder generó contexto para el Planner:")
    print(initial_context)

    # 5b. Generar el Plan
    capabilities = await registry.get_all()
    plan_response = await planner.plan(goal, initial_context, capabilities)
    logger.info(f"Planner generó un plan con ID: {plan_response.plan_id}")

    # 5c. Ejecutar paso a paso y evaluar (Planner -> Executor -> Reviewer)
    for step in plan_response.steps:
        logger.info(f"Iniciando Paso {step.step_id}: '{step.task}'")

        # Simular los inputs del paso
        inputs = {"query": "Traefik"} if step.capability_name == "search_knowledge" else {"message": "Puerto encontrado: 443"}

        # Executor ejecuta el paso
        step.status = "running"
        output = await executor.execute_step(step, inputs)
        step.actual_output = output
        step.status = "completed"

        logger.info(f"Executor retornó salida para Paso {step.step_id}:")
        print(f"--> {output[:200]}...")

        # Reviewer evalúa
        logger.info(f"Reviewer evaluando Paso {step.step_id}...")
        review = await reviewer.review_step(step.task, step.expected_output, output)

        if review.approved:
            logger.info(f"[APROBADO] Paso {step.step_id} superado con éxito.")
        else:
            logger.warning(f"[RECHAZADO] Paso {step.step_id} falló. Feedback: {review.feedback}")
            step.status = "failed"
            break

    logger.info("Simulación del ciclo de vida completada con éxito.")

if __name__ == "__main__":
    asyncio.run(run_simulation())
