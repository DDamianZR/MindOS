
from mindos_schemas.capabilities import Capability

from agents.src.application.registry.capability_registry_port import CapabilityRegistryPort


class InMemoryCapabilityRegistry(CapabilityRegistryPort):
    """
    Implementación en memoria de CapabilityRegistryPort para la simulación
    y registro dinámico de herramientas en el ecosistema.
    """
    def __init__(self):
        self._capabilities: dict[str, Capability] = {}

    async def register(self, capabilities: list[Capability]) -> bool:
        for cap in capabilities:
            self._capabilities[cap.name] = cap
        return True

    async def get_all(self) -> list[Capability]:
        return list(self._capabilities.values())

    async def get_by_name(self, name: str) -> Capability | None:
        return self._capabilities.get(name)
