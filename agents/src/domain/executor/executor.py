from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from mindos_schemas.api.v1.agent_dto import PlanStep


@dataclass
class ExecutionResult:
    """
    Resultado de ejecutar un paso del plan.

    `status` distingue si el paso quedó `completed`/`failed` (el Reviewer lo evalúa a
    continuación) o `pending_approval` (F1-T8: la capacidad exige consentimiento humano;
    el grafo se detiene sin pasar por revisión hasta que se resuelva la aprobación).
    """
    output: str
    status: str = "completed"


class Executor(ABC):
    """
    Abstracción de la capa de Ejecución (Executor).
    Su responsabilidad es despachar la ejecución de un paso del plan. Utiliza el registro
    de capacidades para resolver cómo y dónde llamar a la habilidad necesaria y retornar el
    resultado crudo junto con el estado resultante del paso.
    """
    @abstractmethod
    async def execute_step(self, step: PlanStep, inputs: dict[str, Any]) -> ExecutionResult:
        """
        Resuelve la capacidad requerida por el paso, ejecuta la petición
        contra el servicio proveedor y retorna el resultado.
        """
        pass
