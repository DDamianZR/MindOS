from uuid import UUID

import httpx
from mindos_common.logging import get_logger

from agents.src.application.ports.reasoning_recorder import ReasoningRecorderPort

logger = get_logger("http_reasoning_recorder")


class HttpReasoningRecorder(ReasoningRecorderPort):
    """
    Implementación real de ReasoningRecorderPort (F2-T2): despacha el registro del episodio
    al Thinking Graph del Memory Service vía HTTP.

    Best-effort: si el Memory Service no responde, se registra una advertencia pero NO se
    interrumpe la ejecución del agente — perder la traza de razonamiento es preferible a que
    una meta del usuario falle porque el servicio de memoria esté temporalmente caído.
    """
    def __init__(self, base_url: str, http_client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self._http_client = http_client or httpx.AsyncClient(timeout=10.0)

    async def _post(self, path: str, json_body: dict) -> None:
        try:
            response = await self._http_client.post(f"{self.base_url}{path}", json=json_body)
            response.raise_for_status()
        except Exception as e:
            logger.warning("No se pudo registrar la traza de razonamiento", path=path, error=str(e))

    async def start_episode(self, episode_id: UUID, goal: str, correlation_id: UUID, agent: str) -> None:
        await self._post("/api/v1/thinking/episodes", {
            "episode_id": str(episode_id), "goal": goal,
            "correlation_id": str(correlation_id), "agent": agent,
        })

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
        await self._post(f"/api/v1/thinking/episodes/{episode_id}/steps", {
            "step_id": str(step_id), "step_index": step_index, "kind": kind,
            "input": input_text, "output": output_text, "capability_name": capability_name,
            "approved": approved, "feedback": feedback,
            "knowledge_refs": [str(r) for r in (knowledge_refs or [])],
        })

    async def close_episode(self, episode_id: UUID, status: str, final_output: str | None = None) -> None:
        await self._post(f"/api/v1/thinking/episodes/{episode_id}/close", {
            "status": status, "final_output": final_output,
        })

    async def close(self) -> None:
        """Cierra el cliente HTTP interno."""
        await self._http_client.aclose()
