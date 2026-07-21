from uuid import UUID

import pytest
from mindos_schemas.api.v1.agent_dto import GeneratePlanResponse, PlanStep, ReviewStepResponse
from mindos_schemas.capabilities import Capability

from agents.src.domain.executor.executor import ExecutionResult, Executor
from agents.src.domain.planner.agent_graph import AgentState, PlannerExecutorReviewerGraph
from agents.src.domain.planner.planner import Planner
from agents.src.domain.planner.reviewer import Reviewer


# Mock del Planner
class DummyPlanner(Planner):
    def __init__(self):
        self.call_count = 0

    async def plan(self, goal, context, available_capabilities):
        self.call_count += 1
        # Generar un plan básico
        return GeneratePlanResponse(
            plan_id=UUID("018b10f8-e1a5-7b18-b2a6-382a93414902"),
            goal=goal,
            steps=[
                PlanStep(
                    step_id=1,
                    task="Paso de prueba",
                    capability_name="search_knowledge",
                    expected_output="Output esperado",
                    status="pending"
                )
            ]
        )


# Mock del Reviewer
class DummyReviewer(Reviewer):
    def __init__(self, approved=True, feedback=None):
        self.approved = approved
        self.feedback = feedback

    async def review_step(self, task, expected_output, actual_output):
        return ReviewStepResponse(approved=self.approved, feedback=self.feedback)


# Mock del Executor
class DummyExecutor(Executor):
    async def execute_step(self, step, inputs):
        return ExecutionResult(output="Resultado de ejecución del executor", status="completed")


@pytest.mark.asyncio
async def test_agent_graph_execution_success():
    # 1. Instanciar Mocks
    planner = DummyPlanner()
    reviewer = DummyReviewer(approved=True)
    executor = DummyExecutor()

    # 2. Construir Grafo
    graph_workflow = PlannerExecutorReviewerGraph(planner, executor, reviewer)
    compiled_graph = graph_workflow.graph

    # 3. Definir estado inicial
    cap = Capability(
        name="search_knowledge",
        description="Búsqueda",
        parameters_schema={},
        provider_service="memory",
        endpoint_path="/api"
    )

    initial_state = AgentState(
        goal="Lograr meta de prueba",
        context="Contexto base",
        plan_id=None,
        steps=[],
        current_step_idx=0,
        available_capabilities=[cap],
        inputs={},
        feedback=None,
        error=None,
        final_output=None
    )

    # 4. Invocar Grafo
    result = await compiled_graph.ainvoke(initial_state)

    # 5. Validar que completó exitosamente y se aprobó el paso
    assert result["error"] is None
    assert result["feedback"] is None
    assert result["current_step_idx"] == 1
    assert len(result["steps"]) == 1
    assert result["steps"][0].status == "completed"
    assert result["final_output"] == "Resultado de ejecución del executor"
    assert planner.call_count == 1  # Planificado 1 vez


@pytest.mark.asyncio
async def test_agent_graph_execution_replan_on_reject():
    # 1. Instanciar Mocks (El revisor rechaza el paso en la primera ejecución)
    planner = DummyPlanner()
    reviewer = DummyReviewer(approved=False, feedback="El output es incorrecto")
    executor = DummyExecutor()

    # 2. Construir Grafo
    graph_workflow = PlannerExecutorReviewerGraph(planner, executor, reviewer)
    compiled_graph = graph_workflow.graph

    cap = Capability(
        name="search_knowledge",
        description="Búsqueda",
        parameters_schema={},
        provider_service="memory",
        endpoint_path="/api"
    )

    initial_state = AgentState(
        goal="Lograr meta de prueba",
        context="Contexto base",
        plan_id=None,
        steps=[],
        current_step_idx=0,
        available_capabilities=[cap],
        inputs={},
        feedback=None,
        error=None,
        final_output=None
    )

    # 3. Para evitar bucle infinito en el test de replanificación, mockearemos
    # el comportamiento del revisor para que la segunda vez apruebe
    # Pero dado que LangGraph se ejecuta síncronamente, podemos verificar la replanificación
    # interceptando el flujo.
    # En este caso, para no entrar en bucle infinito, cambiamos la aprobación del Reviewer
    # dinámicamente cuando el planner es llamado por segunda vez.
    original_plan = planner.plan
    async def intercept_plan(goal, context, available_capabilities):
        # Cuando se llama por segunda vez, configuramos el reviewer para que apruebe el paso
        if planner.call_count == 1:
            reviewer.approved = True
            reviewer.feedback = None
        return await original_plan(goal, context, available_capabilities)

    planner.plan = intercept_plan

    # 4. Invocar Grafo
    result = await compiled_graph.ainvoke(initial_state)

    # 5. Validar que se llamó al Planner una segunda vez tras el rechazo
    assert planner.call_count == 2  # Primera planificación + Replanning por desaprobación
    assert result["current_step_idx"] == 1
    assert result["feedback"] is None
    assert result["error"] is None


@pytest.mark.asyncio
async def test_agent_graph_stops_after_max_retries():
    """F0-T8: un Reviewer que SIEMPRE rechaza debe terminar de forma controlada en <= max_retries,
    sin colgarse ni exceder el límite de recursión."""
    planner = DummyPlanner()
    reviewer = DummyReviewer(approved=False, feedback="Nunca es suficiente")
    executor = DummyExecutor()

    graph_workflow = PlannerExecutorReviewerGraph(planner, executor, reviewer)
    compiled_graph = graph_workflow.graph

    cap = Capability(
        name="search_knowledge", description="Búsqueda", parameters_schema={},
        provider_service="memory", endpoint_path="/api"
    )
    initial_state = AgentState(
        goal="Meta imposible de aprobar", context="Contexto base", plan_id=None, steps=[],
        current_step_idx=0, available_capabilities=[cap], inputs={}, feedback=None,
        error=None, final_output=None, retries=0, max_retries=3
    )

    result = await compiled_graph.ainvoke(initial_state)

    # Terminó de forma controlada (no excepción de recursión) con error y final_output explicativos
    assert result["retries"] == 3
    assert result["error"] is not None
    assert "máximo de reintentos" in result["final_output"]
    # No debe haber replanificado más de max_retries veces
    assert planner.call_count <= 3 + 1


class NeverCalledReviewer(Reviewer):
    """Falla si se invoca: no debe haber nada que revisar cuando el paso está pending_approval."""
    async def review_step(self, task, expected_output, actual_output):
        raise AssertionError("El Reviewer no debe invocarse cuando el paso queda pending_approval")


class PendingApprovalExecutor(Executor):
    async def execute_step(self, step, inputs):
        return ExecutionResult(output="Requiere aprobación humana", status="pending_approval")


@pytest.mark.asyncio
async def test_agent_graph_stops_at_pending_approval_without_reviewing():
    """F1-T8: cuando el Executor devuelve pending_approval, el grafo se detiene de inmediato
    sin llamar al Reviewer (no hay nada que revisar todavía) ni avanzar de paso."""
    planner = DummyPlanner()
    reviewer = NeverCalledReviewer()
    executor = PendingApprovalExecutor()

    graph_workflow = PlannerExecutorReviewerGraph(planner, executor, reviewer)
    compiled_graph = graph_workflow.graph

    cap = Capability(
        name="search_knowledge", description="Búsqueda", parameters_schema={},
        provider_service="memory", endpoint_path="/api", requires_approval=True,
    )
    initial_state = AgentState(
        goal="Acción sensible", context="Contexto base", plan_id=None, steps=[],
        current_step_idx=0, available_capabilities=[cap], inputs={}, feedback=None,
        error=None, final_output=None, retries=0, max_retries=3
    )

    result = await compiled_graph.ainvoke(initial_state)

    assert result["steps"][0].status == "pending_approval"
    assert result["current_step_idx"] == 0, "no debe avanzar de paso sin revisión/aprobación"
    assert result["final_output"] is not None
    assert "aprobación" in result["final_output"].lower()
    assert result["error"] is None
