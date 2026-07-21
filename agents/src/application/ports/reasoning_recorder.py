from abc import ABC, abstractmethod
from uuid import UUID


class ReasoningRecorderPort(ABC):
    """
    Puerto para registrar la traza de razonamiento de un episodio Planner→Executor→Reviewer
    en el Thinking Graph del Memory Service (F2-T2). El grafo de LangGraph (`agent_graph.py`)
    depende únicamente de esta abstracción — nunca escribe en la base de datos de Memory
    directamente, preservando la separación hexagonal entre servicios.
    """
    @abstractmethod
    async def start_episode(self, episode_id: UUID, goal: str, correlation_id: UUID, agent: str) -> None:
        """Inicia el registro de un nuevo episodio de razonamiento."""
        pass

    @abstractmethod
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
        """Registra un paso del episodio."""
        pass

    @abstractmethod
    async def close_episode(self, episode_id: UUID, status: str, final_output: str | None = None) -> None:
        """Cierra el episodio con su estado y resultado final."""
        pass
