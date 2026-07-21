from uuid import UUID

from agents.src.application.ports.reasoning_recorder import ReasoningRecorderPort


class NoOpReasoningRecorder(ReasoningRecorderPort):
    """
    Implementación nula de ReasoningRecorderPort: no persiste nada. Es el default de
    `PlannerExecutorReviewerGraph` para no forzar a cada test/uso a depender del Memory
    Service; la grabación real se inyecta explícitamente (ver `HttpReasoningRecorder`).
    """
    async def start_episode(self, episode_id: UUID, goal: str, correlation_id: UUID, agent: str) -> None:
        pass

    async def record_step(
        self,
        episode_id: UUID,
        step_id: UUID,
        step_index: int,
        kind: str,
        input_text: str | None,
        output_text: str | None,
        capability_name: str | None = None,
        approved: bool | None = None,
        feedback: str | None = None,
        knowledge_refs: list[UUID] | None = None,
    ) -> None:
        pass

    async def close_episode(self, episode_id: UUID, status: str, final_output: str | None = None) -> None:
        pass
