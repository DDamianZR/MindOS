from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from mindos_common.context import set_correlation_id
from mindos_common.ids import new_id
from mindos_common.logging import configure_logging, get_logger
from mindos_schemas.api.v1.memory_dto import ContextBundle
from mindos_schemas.capabilities import (
    Capability,
    RegisterCapabilitiesRequest,
    RegisterCapabilitiesResponse,
)

from agents.src.config import settings
from agents.src.domain.executor.capability_executor import CapabilityExecutor
from agents.src.domain.planner.agent_graph import AgentState, PlannerExecutorReviewerGraph
from agents.src.domain.planner.llm_planner import LlmPlanner
from agents.src.domain.planner.llm_reviewer import LlmReviewer
from agents.src.infrastructure.adapters.in_memory_capability_registry import (
    InMemoryCapabilityRegistry,
)
from agents.src.infrastructure.adapters.mock_llm import MockLlm
from agents.src.infrastructure.adapters.ollama_llm import OllamaLlm

configure_logging("AgentsService", settings.MINDOS_ENV)
logger = get_logger("agents_main")

app = FastAPI(
    title="MindOS Agents Service",
    description="Motor de Orquestación y Grafos de Decisión Cognitivos de MindOS",
    version="1.0.0"
)

# Registro de capacidades global en memoria del servicio
capability_registry = InMemoryCapabilityRegistry()

def get_llm_port():
    """Inyecta el LLM configurado (Ollama local o Mock)."""
    # Si la variable de entorno nos dice que usemos Ollama real
    if settings.MINDOS_ENV == "production":
        return OllamaLlm(model_name=settings.OLLAMA_MODEL, base_url=settings.OLLAMA_URL)
    return MockLlm()


def resolve_service_url(provider_service: str) -> str | None:
    """
    Resuelve el `provider_service` de una Capability (ej: 'memory') a la URL base del
    servicio que la implementa (F1-T8). Servicios futuros (Fase 3+: whatsapp, comms...)
    se suman aquí a medida que existan.
    """
    known_services = {"memory": settings.MEMORY_URL}
    return known_services.get(provider_service)

@app.get("/health")
async def health():
    """Liveness básico para healthchecks de Docker/Traefik."""
    return {"status": "ok", "service": "agents", "env": settings.MINDOS_ENV}


@app.post("/api/v1/capabilities/register", response_model=RegisterCapabilitiesResponse)
async def register_capabilities(request: RegisterCapabilitiesRequest):
    logger.info("Recibida solicitud de registro de capacidades", count=len(request.capabilities))

    success = await capability_registry.register(request.capabilities)
    names = [cap.name for cap in request.capabilities]

    return RegisterCapabilitiesResponse(
        success=success,
        registered_names=names
    )

@app.post("/api/v1/agents/execute", status_code=status.HTTP_200_OK)
async def execute_agent_goal(
    goal: str,
    correlation_id: UUID | None = None,
    llm=Depends(get_llm_port)
):
    # Generar o propagar el correlation_id (UUIDv7)
    corr_id = correlation_id or new_id()
    set_correlation_id(corr_id)

    logger.info("Iniciando ejecución de meta para el usuario", goal=goal, correlation_id=str(corr_id))

    # 1. Recuperar contexto GraphRAG (F1-T7) de forma dinámica desde el Memory Service vía HTTP.
    # El Context Builder v2 combina similitud vectorial + expansión por grafo + reranking por
    # importancia/recencia/confianza, y devuelve fragmentos citables (node_id/source).
    memory_context_url = f"{settings.MEMORY_URL}/api/v1/memory/context"
    # Fallback local para desarrollo fuera del bridge
    fallback_url = "http://localhost:8001/api/v1/memory/context"

    initial_context = "No hay contexto disponible de forma síncrona."
    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in [memory_context_url, fallback_url]:
            try:
                response = await client.post(url, json={"query": goal, "limit": 3, "depth": 1})
                if response.status_code == 200:
                    bundle = ContextBundle.model_validate(response.json())
                    initial_context = bundle.to_prompt()
                    logger.info(
                        "Contexto GraphRAG recuperado con éxito de la memoria",
                        fragments=len(bundle.fragments)
                    )
                    break
            except Exception:
                pass

    # 2. Inicializar componentes del grafo LangGraph. El Executor despacha capacidades reales
    # (F1-T8) vía HTTP contra el servicio resuelto de `resolve_service_url`.
    planner = LlmPlanner(llm)
    reviewer = LlmReviewer(llm)
    executor = CapabilityExecutor(capability_registry, service_url_resolver=resolve_service_url)

    # 3. Compilar y ejecutar el grafo asíncronamente
    agent_graph = PlannerExecutorReviewerGraph(planner, executor, reviewer)
    compiled_flow = agent_graph.graph

    available_caps = await capability_registry.get_all()

    # Si no hay capacidades en el registro, inyectar por defecto la de búsqueda
    if not available_caps:
        search_cap = Capability(
            name="search_knowledge",
            description="Busca en la base semántica y grafo de conocimiento de MindOS",
            parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            provider_service="memory",
            endpoint_path="/api/v1/memory/search"
        )
        available_caps = [search_cap]
        await capability_registry.register([search_cap])

    initial_state = AgentState(
        goal=goal,
        context=initial_context,
        plan_id=None,
        steps=[],
        current_step_idx=0,
        available_capabilities=available_caps,
        inputs={"query": goal},
        feedback=None,
        error=None,
        final_output=None,
        retries=0,
        max_retries=3
    )

    try:
        final_state = await compiled_flow.ainvoke(initial_state)

        # Estructurar la respuesta
        return {
            "plan_id": final_state.get("plan_id"),
            "goal": final_state.get("goal"),
            "steps": [
                {
                    "step_id": s.step_id,
                    "task": s.task,
                    "status": s.status,
                    "actual_output": s.actual_output
                } for s in final_state.get("steps", [])
            ],
            "output": final_state.get("final_output"),
            "correlation_id": corr_id
        }

    except Exception as e:
        logger.error("Error catastrófico en la ejecución del grafo de agentes", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fallo crítico en el motor de planificación: {str(e)}"
        ) from e
    finally:
        await executor.close()

# Importaciones complementarias necesarias
