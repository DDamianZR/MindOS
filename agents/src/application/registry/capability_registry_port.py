from abc import ABC, abstractmethod

from mindos_schemas.capabilities import Capability


class CapabilityRegistryPort(ABC):
    """
    Puerto que abstrae la gestión dinámica de habilidades del ecosistema.
    Permite desacoplar al Planner de la infraestructura física del registro.
    """
    @abstractmethod
    async def register(self, capabilities: list[Capability]) -> bool:
        """
        Registra una lista de habilidades de un servicio en el ecosistema.
        """
        pass

    @abstractmethod
    async def get_all(self) -> list[Capability]:
        """
        Recupera el listado completo de capacidades activas.
        """
        pass

    @abstractmethod
    async def get_by_name(self, name: str) -> Capability | None:
        """
        Busca una capacidad específica por su nombre único.
        """
        pass
#
