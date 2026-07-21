from typing import Any

from mindos_schemas.api.v1.agent_dto import PlanStep

from agents.src.application.registry.capability_registry_port import CapabilityRegistryPort
from agents.src.domain.executor.executor import Executor


class CapabilityExecutor(Executor):
    """
    Implementación concreta de Executor que despacha la ejecución
    utilizando el CapabilityRegistry para determinar el destino y formato de la llamada.
    """
    def __init__(self, registry: CapabilityRegistryPort):
        self.registry = registry
        # Manejadores locales registrados para simulación In-Memory
        self._mock_handlers: dict[str, Any] = {}

    def register_mock_handler(self, capability_name: str, handler_callable) -> None:
        """Permite registrar un mock ejecutable en memoria para pruebas de la Fase 2."""
        self._mock_handlers[capability_name] = handler_callable

    async def execute_step(self, step: PlanStep, inputs: dict[str, Any]) -> str:
        if not step.capability_name:
            return f"Error: El paso {step.step_id} no especifica una capacidad de ejecución."

        cap = await self.registry.get_by_name(step.capability_name)
        if not cap:
            return f"Error: La capacidad '{step.capability_name}' no está registrada en el ecosistema."

        # Simulación de ejecución en memoria
        if cap.name in self._mock_handlers:
            handler = self._mock_handlers[cap.name]
            try:
                # Ejecutar el handler simulado pasándole los inputs
                result = await handler(inputs)
                return str(result)
            except Exception as e:
                return f"Excepción durante la ejecución de la capacidad {cap.name}: {str(e)}"

        return f"[Simulación] Capacidad '{cap.name}' ejecutada en servicio '{cap.provider_service}' vía '{cap.endpoint_path}' con parámetros: {inputs}."
