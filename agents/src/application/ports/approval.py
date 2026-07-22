from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class ApprovalPort(ABC):
    """
    Puerto de persistencia de aprobaciones (F1-T8/F3-T1/F3-T7): cuando una capacidad
    `requires_approval` se pausa, se crea aquí un registro durable con todo lo necesario
    para, más tarde (vía Gateway), resolverla y — si se aprueba — despachar la capacidad
    diferida con sus inputs originales.
    """
    @abstractmethod
    async def create(
        self,
        approval_id: UUID,
        episode_id: UUID,
        step_id: int,
        capability_name: str,
        inputs: dict[str, Any],
        reply_to: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def get(self, approval_id: UUID) -> dict[str, Any] | None:
        pass

    @abstractmethod
    async def list_pending(self) -> list[dict[str, Any]]:
        """Aprobaciones con `status='pending'`, más recientes primero (bandeja del Dashboard, F4-T1)."""
        pass

    @abstractmethod
    async def resolve(
        self, approval_id: UUID, status: str, result_output: str | None = None
    ) -> dict[str, Any] | None:
        """`status` es 'approved' o 'rejected'. Devuelve `None` si no existe o ya estaba resuelta."""
        pass
