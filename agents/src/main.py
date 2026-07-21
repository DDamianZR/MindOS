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
from agents.src.infrastructure.adapters.http_reasoning_recorder import HttpReasoningRecorder
from agents.src.infrastructure.adapters.in_memory_approval_store import InMemoryApprovalStore
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
# Aprobaciones pendientes (F1-T8/F3-T1/F3-T7), resueltas vía Gateway.
approval_store = InMemoryApprovalStore()

def get_llm_port():
    """Inyecta el LLM configurado (Ollama local o Mock)."""
    # Si la variable de entorno nos dice que usemos Ollama real
    if settings.MINDOS_ENV == "production":
        return OllamaLlm(model_name=settings.OLLAMA_MODEL, base_url=settings.OLLAMA_URL)
    return MockLlm()


async def get_http_client():
    """
    Cliente HTTP compartido hacia otros servicios (Memory), inyectado vía FastAPI `Depends`.
    Centralizar esto (en vez de crear un `httpx.AsyncClient` ad-hoc por llamada) permite:
    reutilizar conexiones dentro de un mismo request, e inyectar un transporte de prueba
    (`app.dependency_overrides[get_http_client]`) en tests de integración.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        yield client


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
    reply_to_provider: str | None = None,
    reply_to_sender_id: str | None = None,
    llm=Depends(get_llm_port),
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    # Generar o propagar el correlation_id (UUIDv7)
    corr_id = correlation_id or new_id()
    set_correlation_id(corr_id)

    # F3-T7: si el goal vino de un mensaje entrante (pipeline F3-T5), el canal de origen viaja
    # aquí para poder notificar por el mismo canal si una capacidad queda pendiente de aprobación.
    reply_to = (
        {"provider": reply_to_provider, "sender_id": reply_to_sender_id}
        if reply_to_provider and reply_to_sender_id else None
    )

    logger.info("Iniciando ejecución de meta para el usuario", goal=goal, correlation_id=str(corr_id))

    # 1. Recuperar contexto GraphRAG (F1-T7) de forma dinámica desde el Memory Service vía HTTP.
    # El Context Builder v2 combina similitud vectorial + expansión por grafo + reranking por
    # importancia/recencia/confianza, y devuelve fragmentos citables (node_id/source).
    memory_context_url = f"{settings.MEMORY_URL}/api/v1/memory/context"
    # Fallback local para desarrollo fuera del bridge
    fallback_context_url = "http://localhost:8001/api/v1/memory/context"

    initial_context = "No hay contexto disponible de forma síncrona."
    context_node_ids: list[UUID] = []
    for url in [memory_context_url, fallback_context_url]:
        try:
            response = await http_client.post(url, json={"query": goal, "limit": 3, "depth": 1})
            if response.status_code == 200:
                bundle = ContextBundle.model_validate(response.json())
                initial_context = bundle.to_prompt()
                context_node_ids = [f.node_id for f in bundle.fragments]
                logger.info(
                    "Contexto GraphRAG recuperado con éxito de la memoria",
                    fragments=len(bundle.fragments)
                )
                break
        except Exception:
            pass

    # 2. Inicializar componentes del grafo LangGraph. El Executor despacha capacidades reales
    # (F1-T8) vía HTTP contra el servicio resuelto de `resolve_service_url`. El recorder (F2-T2)
    # persiste la traza de razonamiento (episodio + pasos) en el Thinking Graph del Memory Service.
    planner = LlmPlanner(llm)
    reviewer = LlmReviewer(llm)
    executor = CapabilityExecutor(
        capability_registry, service_url_resolver=resolve_service_url, http_client=http_client,
        approval_store=approval_store,
    )
    recorder = HttpReasoningRecorder(settings.MEMORY_URL, http_client=http_client)

    # 3. Compilar y ejecutar el grafo asíncronamente
    agent_graph = PlannerExecutorReviewerGraph(planner, executor, reviewer, recorder=recorder)
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
        max_retries=3,
        correlation_id=corr_id,
        context_node_ids=context_node_ids,
        reasoning_step_counter=0,
        reply_to=reply_to,
    )

    try:
        final_state = await compiled_flow.ainvoke(initial_state)

        # Cerrar el episodio de razonamiento (F2-T2) con su estado terminal real.
        if final_state.get("error"):
            episode_status = "failed"
        elif any(s.status == "pending_approval" for s in final_state.get("steps", [])):
            episode_status = "pending_approval"
        else:
            episode_status = "completed"
        await recorder.close_episode(corr_id, status=episode_status, final_output=final_state.get("final_output"))

        # Si el episodio concluyó con éxito, promover el resultado a conocimiento citable
        # (nodo 'outcome'), evidenciado por los nodos de contexto que lo sustentaron. Esto es lo
        # que hace que "el final_output quede ligado a las evidencias" (DoD F2-T2).
        if episode_status == "completed" and final_state.get("final_output"):
            await _record_outcome_as_knowledge(
                http_client=http_client, recorder=recorder, goal=goal,
                final_output=final_state["final_output"], context_node_ids=context_node_ids,
                episode_id=corr_id, correlation_id=corr_id,
                step_index=final_state.get("reasoning_step_counter", 0),
            )

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
    # Nota: no se cierra `http_client` aquí — es compartido (executor/recorder/outcome) e
    # inyectado vía `Depends(get_http_client)`; su ciclo de vida lo gestiona esa dependencia.


async def _record_outcome_as_knowledge(
    http_client: httpx.AsyncClient,
    recorder: HttpReasoningRecorder,
    goal: str,
    final_output: str,
    context_node_ids: list[UUID],
    episode_id: UUID,
    correlation_id: UUID,
    step_index: int,
) -> None:
    """
    F2-T2: promueve el resultado de un episodio exitoso a un nodo de conocimiento citable
    (`object_type=outcome`), enlazado por `EVIDENCES` a los nodos de contexto que lo
    sustentaron. Best-effort: si el Memory Service no responde, se registra una advertencia
    pero no se interrumpe la respuesta al usuario (que ya tiene su resultado).
    """
    outcome_title = f"Resultado: {goal}"[:255]

    for base_url in [settings.MEMORY_URL, "http://localhost:8001"]:
        try:
            ingest_resp = await http_client.post(
                f"{base_url}/api/v1/memory/ingest",
                headers={"X-Correlation-Id": str(correlation_id)},
                json={
                    "object_type": "outcome",
                    "title": outcome_title,
                    "content": final_output,
                    "author": "AgentsService",
                    "evidence": [{"node_id": str(n), "weight": 1.0} for n in context_node_ids],
                    "metadata": {"episode_id": str(episode_id)},
                },
            )
            ingest_resp.raise_for_status()
            outcome_node_id = ingest_resp.json()["node_id"]

            for context_node_id in context_node_ids:
                rel_resp = await http_client.post(
                    f"{base_url}/api/v1/memory/relation",
                    headers={"X-Correlation-Id": str(correlation_id)},
                    json={
                        "source_id": str(context_node_id), "target_id": outcome_node_id,
                        "relation_type": "EVIDENCES",
                    },
                )
                rel_resp.raise_for_status()

            # Enlaza el episodio con el nodo que produjo (F2-T3: /explain debe poder mostrar,
            # a partir del nodo 'outcome', qué corrida de agente lo generó — no solo qué lo
            # evidencia en el Knowledge Graph).
            await recorder.record_step(
                episode_id=episode_id, step_id=new_id(), step_index=step_index, kind="conclude",
                input_text=goal, output_text=f"Nodo de conocimiento creado: {outcome_node_id}",
                knowledge_refs=[UUID(outcome_node_id)],
            )

            logger.info(
                "Resultado del episodio promovido a conocimiento",
                outcome_node_id=outcome_node_id, evidences=len(context_node_ids)
            )
            return
        except Exception as e:
            logger.warning("No se pudo registrar el resultado como conocimiento", error=str(e))


# Import al final (evita ciclo): el router importa de este módulo (approval_store,
# capability_registry, get_http_client, resolve_service_url), mismo patrón que memory/src/main.py.
from agents.src.api.approvals_router import router as approvals_router  # noqa: E402

app.include_router(approvals_router)

# Fin del módulo main
