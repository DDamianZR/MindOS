from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from agents.src.application.ports.approval import ApprovalPort


class InMemoryApprovalStore(ApprovalPort):
    """Implementación en memoria de ApprovalPort. Suficiente para un Agents Service de un proceso;
    una implementación Postgres se puede añadir sin cambiar el contrato si el volumen lo exige."""
    def __init__(self):
        self._approvals: dict[UUID, dict[str, Any]] = {}

    async def create(
        self,
        approval_id: UUID,
        episode_id: UUID,
        step_id: int,
        capability_name: str,
        inputs: dict[str, Any],
        reply_to: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": approval_id,
            "episode_id": episode_id,
            "step_id": step_id,
            "capability_name": capability_name,
            "inputs": inputs,
            "status": "pending",
            "reply_to": reply_to,
            "created_at": datetime.now(timezone.utc),
            "resolved_at": None,
            "result_output": None,
        }
        self._approvals[approval_id] = record
        return record

    async def get(self, approval_id: UUID) -> dict[str, Any] | None:
        return self._approvals.get(approval_id)

    async def list_pending(self) -> list[dict[str, Any]]:
        pending = [r for r in self._approvals.values() if r["status"] == "pending"]
        return sorted(pending, key=lambda r: r["created_at"], reverse=True)

    async def resolve(
        self, approval_id: UUID, status: str, result_output: str | None = None
    ) -> dict[str, Any] | None:
        record = self._approvals.get(approval_id)
        if not record or record["status"] != "pending":
            return None
        record["status"] = status
        record["resolved_at"] = datetime.now(timezone.utc)
        record["result_output"] = result_output
        return record
