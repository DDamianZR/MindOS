from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from memory.src.application.ports.thinking_graph import ThinkingGraphPort


class InMemoryThinkingGraph(ThinkingGraphPort):
    """
    Implementación en memoria de ThinkingGraphPort para simulación y pruebas del Kernel.
    Mantiene episodios y sus pasos en diccionarios, indexados por `knowledge_refs` para
    resolver `get_episodes_by_node` / `walk_reasoning` sin recorrer todo el histórico.
    """
    def __init__(self):
        self._episodes: dict[UUID, dict[str, Any]] = {}
        self._steps: dict[UUID, list[dict[str, Any]]] = {}  # episode_id -> [step, ...]

    async def create_episode(self, episode_id: UUID, goal: str, correlation_id: UUID, agent: str) -> None:
        self._episodes[episode_id] = {
            "id": episode_id,
            "goal": goal,
            "correlation_id": correlation_id,
            "agent": agent,
            "status": "running",
            "started_at": datetime.now(timezone.utc),
            "ended_at": None,
            "final_output": None,
        }
        self._steps.setdefault(episode_id, [])

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
        self._steps.setdefault(episode_id, []).append({
            "id": step_id,
            "episode_id": episode_id,
            "step_index": step_index,
            "kind": kind,
            "input": input_text,
            "output": output_text,
            "capability_name": capability_name,
            "approved": approved,
            "feedback": feedback,
            "created_at": datetime.now(timezone.utc),
            "knowledge_refs": list(knowledge_refs or []),
        })

    async def close_episode(self, episode_id: UUID, status: str, final_output: str | None = None) -> None:
        episode = self._episodes.get(episode_id)
        if episode:
            episode["status"] = status
            episode["ended_at"] = datetime.now(timezone.utc)
            episode["final_output"] = final_output

    async def get_episode(self, episode_id: UUID) -> dict[str, Any] | None:
        episode = self._episodes.get(episode_id)
        if not episode:
            return None
        steps = sorted(self._steps.get(episode_id, []), key=lambda s: s["step_index"])
        return {**episode, "steps": steps}

    async def get_episodes_by_node(self, node_id: UUID) -> list[dict[str, Any]]:
        result = []
        for episode_id, episode in self._episodes.items():
            steps = self._steps.get(episode_id, [])
            if any(node_id in step["knowledge_refs"] for step in steps):
                result.append({**episode, "steps": sorted(steps, key=lambda s: s["step_index"])})
        return result

    async def walk_reasoning(self, node_id: UUID) -> list[dict[str, Any]]:
        result = []
        for episode_id, episode in self._episodes.items():
            for step in self._steps.get(episode_id, []):
                if node_id in step["knowledge_refs"]:
                    result.append({**step, "episode_goal": episode["goal"], "episode_agent": episode["agent"]})
        result.sort(key=lambda s: s["created_at"])
        return result
