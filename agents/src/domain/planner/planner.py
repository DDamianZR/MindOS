from abc import ABC, abstractmethod

from mindos_schemas.api.v1.agent_dto import GeneratePlanResponse
from mindos_schemas.capabilities import Capability


class Planner(ABC):
    """
    Abstracción del agente Planificador (Planner).
    Su única responsabilidad es descomponer una meta compleja en un Grafo Acíclico Dirigido (DAG)
    de pasos secuenciales de ejecución, mapeándolos a capacidades disponibles.
    """
    @abstractmethod
    async def plan(
        self,
        goal: str,
        context: str,
        available_capabilities: list[Capability]
    ) -> GeneratePlanResponse:
        """
        Analiza el objetivo y el contexto junto a las habilidades registradas
        para generar un plan estructurado (GeneratePlanResponse).
        """
        pass
