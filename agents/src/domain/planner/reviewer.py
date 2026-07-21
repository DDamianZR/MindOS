from abc import ABC, abstractmethod

from mindos_schemas.api.v1.agent_dto import ReviewStepResponse


class Reviewer(ABC):
    """
    Abstracción del agente Revisor (Reviewer).
    Responsable de evaluar de forma independiente si el resultado real (actual_output)
    producido por el Executor cumple con el resultado esperado (expected_output) para un paso dado.
    """
    @abstractmethod
    async def review_step(
        self,
        task: str,
        expected_output: str,
        actual_output: str
    ) -> ReviewStepResponse:
        """
        Evalúa el paso y retorna la decisión de aprobación junto con la retroalimentación
        si requiere corrección.
        """
        pass
