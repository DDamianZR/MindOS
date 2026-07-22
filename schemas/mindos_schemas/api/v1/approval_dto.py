from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

ApprovalStatus = str  # "pending" | "approved" | "rejected"


class ApprovalRequestDto(BaseModel):
    """Representación de una aprobación pendiente (F1-T8/F3-T1/F3-T7)."""
    id: UUID
    episode_id: UUID
    step_id: int = Field(..., description="PlanStep.step_id (índice secuencial dentro del plan, no UUID)")
    capability_name: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus
    reply_to: dict[str, str] | None = Field(
        default=None, description="Canal de origen para notificar la resolución (provider/sender_id)"
    )
    created_at: datetime
    resolved_at: datetime | None = None
    result_output: str | None = Field(default=None, description="Salida de la capacidad si se aprobó y se ejecutó")


class ResolveApprovalRequest(BaseModel):
    approved: bool = Field(..., description="True para aprobar y ejecutar la capacidad diferida; False para rechazar")
    resolved_by: str | None = Field(default=None, description="Quién resolvió (usuario/canal), informativo")


class ResolveApprovalResponse(BaseModel):
    approval: ApprovalRequestDto
    executed: bool = Field(..., description="Si la capacidad diferida se despachó realmente (solo si approved=True)")


class ListApprovalsResponse(BaseModel):
    """Bandeja de aprobaciones pendientes (F4-T1)."""
    approvals: list[ApprovalRequestDto]
