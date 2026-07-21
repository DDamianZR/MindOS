from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class ThinkingGraphPort(ABC):
    """
    Puerto de infraestructura para el Thinking Graph (F2-T1): el registro del PROCESO de
    razonamiento de los agentes (episodios Planner→Executor→Reviewer y sus pasos), a
    diferencia de `DatabasePort` que registra el RESULTADO (los Objetos Cognitivos).

    Es una abstracción de persistencia pura: no conoce el Knowledge Graph ni camina sus
    relaciones — eso lo compone la capa de aplicación (ver F2-T3, `/explain`).
    """

    @abstractmethod
    async def create_episode(self, episode_id: UUID, goal: str, correlation_id: UUID, agent: str) -> None:
        """Crea un nuevo episodio de razonamiento en estado `running`."""
        pass

    @abstractmethod
    async def append_step(
        self,
        step_id: UUID,
        episode_id: UUID,
        step_index: int,
        kind: str,
        input_text: str | None,
        output_text: str | None,
        capability_name: str | None = None,
        approved: bool | None = None,
        feedback: str | None = None,
        knowledge_refs: list[UUID] | None = None,
    ) -> None:
        """
        Añade un paso (`plan|execute|review|replan`) a un episodio existente.
        `knowledge_refs` son los node_ids del Knowledge Graph citados o creados en este paso.
        """
        pass

    @abstractmethod
    async def close_episode(self, episode_id: UUID, status: str, final_output: str | None = None) -> None:
        """Cierra un episodio: marca `ended_at`, `status` (completed|failed|pending_approval) y el resultado final."""
        pass

    @abstractmethod
    async def get_episode(self, episode_id: UUID) -> dict[str, Any] | None:
        """Recupera un episodio completo con todos sus pasos, ordenados cronológicamente."""
        pass

    @abstractmethod
    async def get_episodes_by_node(self, node_id: UUID) -> list[dict[str, Any]]:
        """
        Episodios (con sus pasos) que referencian `node_id` en `knowledge_refs` de al menos
        uno de sus pasos. Responde "¿qué procesos de razonamiento involucraron este nodo?".
        """
        pass

    @abstractmethod
    async def walk_reasoning(self, node_id: UUID) -> list[dict[str, Any]]:
        """
        Vista aplanada y cronológica de los pasos individuales (no episodios completos) que
        referencian `node_id`, cada uno con el contexto de su episodio (goal, agent). Es la
        traza detallada que alimenta `/explain` (F2-T3): "¿qué pasos del agente tocaron esto?".
        """
        pass
