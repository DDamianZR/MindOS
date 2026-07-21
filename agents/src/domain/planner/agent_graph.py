from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from mindos_common.ids import new_id
from mindos_common.logging import get_logger
from mindos_schemas.api.v1.agent_dto import PlanStep
from mindos_schemas.capabilities import Capability

from agents.src.application.ports.reasoning_recorder import ReasoningRecorderPort
from agents.src.domain.executor.executor import Executor
from agents.src.domain.planner.planner import Planner
from agents.src.domain.planner.reviewer import Reviewer
from agents.src.infrastructure.adapters.noop_reasoning_recorder import NoOpReasoningRecorder

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
    # F2-T2: identidad del episodio de razonamiento (Thinking Graph) y nodos de contexto citados.
    correlation_id: UUID
    context_node_ids: list[UUID]
    reasoning_step_counter: int
    # F3-T7: canal de origen (provider/sender_id) si el goal vino de un mensaje entrante, para
    # poder notificar por el mismo canal cuando una capacidad quede pendiente de aprobación.
    reply_to: dict[str, str] | None


class PlannerExecutorReviewerGraph:
    """
    Definición y compilación del Grafo de decisión de agentes (LangGraph)
    bajo el patrón Planner -> Executor -> Reviewer.

    Cada corrida se registra como un episodio de razonamiento (F2-T2) vía `recorder`, para
    que después pueda explicarse "¿cómo se llegó a esto?" (F2-T3). El registro es opcional
    (`NoOpReasoningRecorder` por defecto) para no forzar esa dependencia en tests/usos que no
    la necesiten.
    """
    def __init__(
        self,
        planner: Planner,
        executor: Executor,
        reviewer: Reviewer,
        recorder: ReasoningRecorderPort | None = None,
    ):
        self.planner = planner
        self.executor = executor
        self.reviewer = reviewer
        self.recorder = recorder or NoOpReasoningRecorder()
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

        is_first_plan = state.get("plan_id") is None
        if is_first_plan:
            await self.recorder.start_episode(
                episode_id=state["correlation_id"], goal=state["goal"],
                correlation_id=state["correlation_id"], agent="AgentsService",
            )

        # Combinar el contexto inicial con la retroalimentación si es una replanificación
        plan_context = state["context"]
        if state.get("feedback"):
            plan_context += f"\n\n[ATENCIÓN - Feedback de Error Anterior]: {state['feedback']}"

        step_idx = state.get("reasoning_step_counter", 0)
        try:
            plan_response = await self.planner.plan(
                goal=state["goal"],
                context=plan_context,
                available_capabilities=state["available_capabilities"]
            )
            await self.recorder.record_step(
                episode_id=state["correlation_id"], step_id=new_id(), step_index=step_idx,
                kind="plan" if is_first_plan else "replan",
                input_text=plan_context, output_text=f"{len(plan_response.steps)} paso(s) generado(s)",
                knowledge_refs=state.get("context_node_ids", []),
            )
            return {
                "plan_id": plan_response.plan_id,
                "steps": plan_response.steps,
                "current_step_idx": 0, # Reiniciar índice de pasos tras replanificación
                "feedback": None,
                "reasoning_step_counter": step_idx + 1,
            }
        except Exception as e:
            logger.error("Error en nodo de planificación", error=str(e))
            await self.recorder.record_step(
                episode_id=state["correlation_id"], step_id=new_id(), step_index=step_idx,
                kind="plan" if is_first_plan else "replan",
                input_text=plan_context, output_text=f"Error: {str(e)}",
            )
            return {"error": f"Fallo al planificar: {str(e)}", "reasoning_step_counter": step_idx + 1}

    async def _execute_node(self, state: AgentState) -> dict[str, Any]:
        """Nodo de Ejecución: Toma el paso actual y ejecuta su capacidad."""
        idx = state["current_step_idx"]
        step = state["steps"][idx]
        logger.info("Nodo [Execute]: Ejecutando paso", step_id=step.step_id, task=step.task)

        step_idx = state.get("reasoning_step_counter", 0)
        step.status = "running"
        try:
            # Despachar ejecución al Executor
            result = await self.executor.execute_step(
                step, state["inputs"], episode_id=state["correlation_id"], reply_to=state.get("reply_to"),
            )
            step.actual_output = result.output
            step.status = result.status

            await self.recorder.record_step(
                episode_id=state["correlation_id"], step_id=new_id(), step_index=step_idx,
                kind="execute", input_text=step.task, output_text=result.output,
                capability_name=step.capability_name, knowledge_refs=state.get("context_node_ids", []),
            )

            if result.status == "pending_approval":
                logger.warning(
                    "Nodo [Execute]: paso en espera de aprobación humana, deteniendo el grafo",
                    step_id=step.step_id
                )
                return {
                    "steps": state["steps"],
                    "reasoning_step_counter": step_idx + 1,
                    "final_output": (
                        f"Ejecución pausada: el paso {step.step_id} requiere aprobación humana "
                        f"antes de continuar. {result.output}"
                    ),
                }
            return {"steps": state["steps"], "reasoning_step_counter": step_idx + 1}
        except Exception as e:
            step.status = "failed"
            logger.error("Error en nodo de ejecución", step_id=step.step_id, error=str(e))
            await self.recorder.record_step(
                episode_id=state["correlation_id"], step_id=new_id(), step_index=step_idx,
                kind="execute", input_text=step.task, output_text=f"Error: {str(e)}",
                capability_name=step.capability_name,
            )
            return {
                "error": f"Fallo al ejecutar paso {step.step_id}: {str(e)}",
                "steps": state["steps"],
                "reasoning_step_counter": step_idx + 1,
            }

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

        step_idx = state.get("reasoning_step_counter", 0)
        try:
            review = await self.reviewer.review_step(
                task=step.task,
                expected_output=step.expected_output,
                actual_output=step.actual_output or ""
            )
            await self.recorder.record_step(
                episode_id=state["correlation_id"], step_id=new_id(), step_index=step_idx,
                kind="review", input_text=step.actual_output, output_text=review.feedback or "Aprobado",
                approved=review.approved, feedback=review.feedback,
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
                    "final_output": final_out,
                    "reasoning_step_counter": step_idx + 1,
                }
            else:
                logger.warning("Nodo [Review]: Paso RECHAZADO", step_id=step.step_id, feedback=review.feedback)
                result = self._retry_or_giveup(
                    state, f"El paso {step.step_id} fue rechazado. Corrección: {review.feedback}"
                )
                result["reasoning_step_counter"] = step_idx + 1
                return result
        except Exception as e:
            logger.error("Error en nodo de revisión", error=str(e))
            await self.recorder.record_step(
                episode_id=state["correlation_id"], step_id=new_id(), step_index=step_idx,
                kind="review", input_text=step.actual_output, output_text=f"Error: {str(e)}",
            )
            result = self._retry_or_giveup(state, f"Error evaluando el paso {step.step_id}: {str(e)}")
            result["reasoning_step_counter"] = step_idx + 1
            return result

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
