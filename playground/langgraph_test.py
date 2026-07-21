import asyncio
from uuid import UUID

from mindos_common.context import set_correlation_id

# Configurar logging
from mindos_common.logging import configure_logging, get_logger

# Importar contratos y grafos
from mindos_schemas.capabilities import Capability

from agents.src.domain.executor.capability_executor import CapabilityExecutor
from agents.src.domain.planner.agent_graph import AgentState, PlannerExecutorReviewerGraph
from agents.src.domain.planner.llm_planner import LlmPlanner
from agents.src.domain.planner.llm_reviewer import LlmReviewer
from agents.src.infrastructure.adapters.in_memory_capability_registry import (
    InMemoryCapabilityRegistry,
)
from agents.src.infrastructure.adapters.mock_llm import MockLlm

configure_logging("LangGraphTest", "INFO")
logger = get_logger("langgraph_test")

async def run_graph_verification():
    correlation_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414909")
    set_correlation_id(correlation_id)

    logger.info("Inicializando componentes para prueba de LangGraph", correlation_id=correlation_id)

    # 1. Registro de capacidades
    registry = InMemoryCapabilityRegistry()
    search_cap = Capability(
        name="search_knowledge",
        description="Busca en la base semántica y grafo de conocimiento de MindOS",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"}
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
                "message": {"type": "string"}
            },
            "required": ["message"]
        },
        provider_service="communication",
        endpoint_path="/api/v1/communication/send"
    )
    await registry.register([search_cap, send_cap])

    # 2. Agentes y Mocks
    mock_llm = MockLlm()
    planner = LlmPlanner(mock_llm)
    reviewer = LlmReviewer(mock_llm)
    executor = CapabilityExecutor(registry)

    # Handlers para las capacidades
    async def mock_handler(inputs):
        return f"[Resultado de búsqueda para '{inputs.get('query')}']: Configuración de Traefik encontrada en puerto 443."

    async def mock_send_handler(inputs):
        return f"[Simulación Chat] Mensaje enviado al usuario: '{inputs.get('message')}'"

    executor.register_mock_handler("search_knowledge", mock_handler)
    executor.register_mock_handler("send_chat_message", mock_send_handler)

    # 3. Compilar Grafo
    agent_flow = PlannerExecutorReviewerGraph(planner, executor, reviewer)
    compiled_graph = agent_flow.graph

    # 4. Definir estado inicial
    initial_state = AgentState(
        goal="Encontrar el puerto configurado de Traefik en el KOS.",
        context="El KOS contiene notas de infraestructura.",
        plan_id=None,
        steps=[],
        current_step_idx=0,
        available_capabilities=[search_cap, send_cap],
        inputs={"query": "Traefik puerto"},
        feedback=None,
        error=None,
        final_output=None
    )

    logger.info("Ejecutando el flujo del Grafo de LangGraph asíncronamente...")

    # Ejecutar el grafo de forma asíncrona
    final_state = await compiled_graph.ainvoke(initial_state)

    logger.info("--- Estado Final del Grafo ---")
    logger.info(f"Goal: {final_state['goal']}")
    logger.info(f"Plan ID: {final_state['plan_id']}")
    logger.info(f"Total Pasos Ejecutados: {len(final_state['steps'])}")
    for step in final_state["steps"]:
        logger.info(f"Paso {step.step_id}: {step.task} -> Estado: {step.status}")
        logger.info(f"   Output: {step.actual_output}")

    logger.info(f"Resultado Final Consolidado: {final_state['final_output']}")

if __name__ == "__main__":
    asyncio.run(run_graph_verification())
