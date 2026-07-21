from abc import ABC, abstractmethod
from typing import Any

from mindos_schemas.api.v1.agent_dto import PlanStep


class Executor(ABC):
    """
    Abstracción de la capa de Ejecución (Executor).
    Su responsabilidad es despachar la ejecución de un paso del plan. Utiliza el registro
    de capacidades para resolver cómo y dónde llamar a la habilidad necesaria y retornar el output crudo.
    """
    @abstractmethod
    async def execute_step(self, step: PlanStep, inputs: dict[str, Any]) -> str:
        """
        Resuelve la capacidad requerida por el paso, ejecuta la petición
        contra el servicio proveedor y retorna el resultado en formato texto.
        """
        pass
#
