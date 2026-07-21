from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from mindos_common.logging import get_logger
from mindos_schemas.api.v1.agent_dto import PlanStep
from mindos_schemas.capabilities import Capability

from agents.src.domain.executor.executor import Executor
from agents.src.domain.planner.planner import Planner
from agents.src.domain.planner.reviewer import Reviewer

logger = get_logger("agent_graph")

class AgentState(TypedDict):
    """
    Estado compartido que viaja a través del grafo de decisión de LangGraph.
    """
    goal: str
    context: str
    plan_id: UUID | None
    steps: list[PlanStep]
    current_step_idx: int
    available_capabilities: list[Capability]
    inputs: dict[str, Any]
    feedback: str | None
    error: str | None
    final_output: str | None
    retries: int
    max_retries: int


class PlannerExecutorReviewerGraph:
    """
    Definición y compilación del Grafo de decisión de agentes (LangGraph)
    bajo el patrón Planner -> Executor -> Reviewer.
    """
    def __init__(self, planner: Planner, executor: Executor, reviewer: Reviewer):
        self.planner = planner
        self.executor = executor
        self.reviewer = reviewer
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        # 1. Definir los nodos del grafo
        workflow.add_node("plan_step", self._plan_node)
        workflow.add_node("execute_step", self._execute_node)
        workflow.add_node("review_step", self._review_node)

        # 2. Configurar el punto de entrada
        workflow.set_entry_point("plan_step")

        # 3. Definir las transiciones (edges)
        workflow.add_edge("plan_step", "execute_step")

        # Enlace condicional tras la ejecución (F1-T8): si el paso quedó pendiente de
        # aprobación humana, el grafo se detiene aquí en vez de pasar a revisión.
        workflow.add_conditional_edges(
            "execute_step",
            self._after_execute,
            {
                "review": "review_step",
                "end": END
            }
        )

        # Enlace condicional desde el Reviewer
        workflow.add_conditional_edges(
            "review_step",
            self._should_continue,
            {
                "continue": "execute_step",
                "replan": "plan_step",
                "end": END
            }
        )

        return workflow.compile()

    async def _plan_node(self, state: AgentState) -> dict[str, Any]:
        """Nodo de Planificación: Llama al Planner para generar o corregir el plan."""
        logger.info("Nodo [Plan]: Generando o refinando plan", goal=state["goal"])

        # Combinar el contexto inicial con la retroalimentación si es una replanificación
        plan_context = state["context"]
        if state.get("feedback"):
            plan_context += f"\n\n[ATENCIÓN - Feedback de Error Anterior]: {state['feedback']}"

        try:
            plan_response = await self.planner.plan(
                goal=state["goal"],
                context=plan_context,
                available_capabilities=state["available_capabilities"]
            )
            return {
                "plan_id": plan_response.plan_id,
                "steps": plan_response.steps,
                "current_step_idx": 0, # Reiniciar índice de pasos tras replanificación
                "feedback": None
            }
        except Exception as e:
            logger.error("Error en nodo de planificación", error=str(e))
            return {"error": f"Fallo al planificar: {str(e)}"}

    async def _execute_node(self, state: AgentState) -> dict[str, Any]:
        """Nodo de Ejecución: Toma el paso actual y ejecuta su capacidad."""
        idx = state["current_step_idx"]
        step = state["steps"][idx]
        logger.info("Nodo [Execute]: Ejecutando paso", step_id=step.step_id, task=step.task)

        step.status = "running"
        try:
            # Despachar ejecución al Executor
            result = await self.executor.execute_step(step, state["inputs"])
            step.actual_output = result.output
            step.status = result.status

            if result.status == "pending_approval":
                logger.warning(
                    "Nodo [Execute]: paso en espera de aprobación humana, deteniendo el grafo",
                    step_id=step.step_id
                )
                return {
                    "steps": state["steps"],
                    "final_output": (
                        f"Ejecución pausada: el paso {step.step_id} requiere aprobación humana "
                        f"antes de continuar. {result.output}"
                    ),
                }
            return {"steps": state["steps"]}
        except Exception as e:
            step.status = "failed"
            logger.error("Error en nodo de ejecución", step_id=step.step_id, error=str(e))
            return {"error": f"Fallo al ejecutar paso {step.step_id}: {str(e)}", "steps": state["steps"]}

    def _after_execute(self, state: AgentState) -> str:
        """F1-T8: si el paso recién ejecutado quedó pendiente de aprobación, detiene el grafo
        en vez de pasar a revisión (no hay nada que revisar todavía)."""
        idx = state["current_step_idx"]
        step = state["steps"][idx]
        if step.status == "pending_approval":
            return "end"
        return "review"

    async def _review_node(self, state: AgentState) -> dict[str, Any]:
        """Nodo de Revisión: Evalúa el output del paso actual."""
        idx = state["current_step_idx"]
        step = state["steps"][idx]
        logger.info("Nodo [Review]: Evaluando resultado de paso", step_id=step.step_id)

        try:
            review = await self.reviewer.review_step(
                task=step.task,
                expected_output=step.expected_output,
                actual_output=step.actual_output or ""
            )

            if review.approved:
                logger.info("Nodo [Review]: Paso APROBADO", step_id=step.step_id)
                next_idx = idx + 1
                final_out = None
                if next_idx >= len(state["steps"]):
                    final_out = step.actual_output or "Meta completada."
                return {
                    "current_step_idx": next_idx,
                    "feedback": None,
                    "final_output": final_out
                }
            else:
                logger.warning("Nodo [Review]: Paso RECHAZADO", step_id=step.step_id, feedback=review.feedback)
                return self._retry_or_giveup(
                    state, f"El paso {step.step_id} fue rechazado. Corrección: {review.feedback}"
                )
        except Exception as e:
            logger.error("Error en nodo de revisión", error=str(e))
            return self._retry_or_giveup(state, f"Error evaluando el paso {step.step_id}: {str(e)}")

    def _retry_or_giveup(self, state: AgentState, reason: str) -> dict[str, Any]:
        """
        Contabiliza un reintento y decide si replanificar o abortar de forma controlada.
        Evita bucles infinitos replan<->execute cuando el Reviewer nunca aprueba.
        """
        retries = state.get("retries", 0) + 1
        max_retries = state.get("max_retries", 3)
        if retries >= max_retries:
            msg = (
                f"Se alcanzó el máximo de reintentos ({max_retries}) sin superar la revisión. "
                f"Último motivo: {reason}"
            )
            logger.error("Nodo [Review]: máximo de reintentos alcanzado, abortando", retries=retries)
            return {"retries": retries, "error": msg, "final_output": msg, "feedback": None}
        return {"retries": retries, "feedback": reason}

    def _should_continue(self, state: AgentState) -> str:
        """Determina la siguiente ruta en base al estado de la revisión."""
        if state.get("error"):
            return "end"

        if state.get("feedback"):
            # Hay feedback de error/rechazo, se requiere replanificar
            return "replan"

        # Si ya se ejecutaron todos los pasos previstos del plan
        if state["current_step_idx"] >= len(state["steps"]):
            return "end"

        # Continuar con el siguiente paso
        return "continue"
