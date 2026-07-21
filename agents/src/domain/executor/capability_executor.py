from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from mindos_common.context import get_correlation_id
from mindos_common.logging import get_logger
from mindos_schemas.api.v1.agent_dto import PlanStep

from agents.src.application.registry.capability_registry_port import CapabilityRegistryPort
from agents.src.domain.executor.executor import ExecutionResult, Executor

logger = get_logger("capability_executor")

ServiceUrlResolver = Callable[[str], str | None]


class CapabilityExecutor(Executor):
    """
    Implementación concreta de Executor que despacha la ejecución utilizando el
    CapabilityRegistry para determinar el destino y formato de la llamada.

    Si la capacidad tiene un handler mock registrado (solo para tests), lo usa. Si no, y el
    `provider_service` resuelve a una URL conocida, hace un despacho HTTP real (F1-T8).
    Si la capacidad exige `requires_approval`, la ejecución se pausa sin despachar nada.
    """
    def __init__(
        self,
        registry: CapabilityRegistryPort,
        service_url_resolver: ServiceUrlResolver | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.registry = registry
        self._mock_handlers: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {}
        self._service_url_resolver = service_url_resolver or (lambda _service: None)
        self._http_client = http_client or httpx.AsyncClient(timeout=15.0)

    def register_mock_handler(self, capability_name: str, handler_callable) -> None:
        """Permite registrar un mock ejecutable en memoria. Uso exclusivo de tests/simulación."""
        self._mock_handlers[capability_name] = handler_callable

    async def execute_step(self, step: PlanStep, inputs: dict[str, Any]) -> ExecutionResult:
        if not step.capability_name:
            return ExecutionResult(
                output=f"Error: El paso {step.step_id} no especifica una capacidad de ejecución.",
                status="failed",
            )

        cap = await self.registry.get_by_name(step.capability_name)
        if not cap:
            return ExecutionResult(
                output=f"Error: La capacidad '{step.capability_name}' no está registrada en el ecosistema.",
                status="failed",
            )

        # Gate de aprobación (F1-T8): capacidades sensibles no se ejecutan sin consentimiento
        # humano. La resolución de la aprobación llega vía Gateway/Dashboard (Fase 3/4).
        if cap.requires_approval:
            logger.warning(
                "Capacidad requiere aprobación humana, ejecución pausada",
                capability=cap.name, step_id=step.step_id
            )
            return ExecutionResult(
                output=f"La capacidad '{cap.name}' requiere aprobación humana antes de ejecutarse.",
                status="pending_approval",
            )

        # Simulación en memoria (exclusivo de tests)
        if cap.name in self._mock_handlers:
            handler = self._mock_handlers[cap.name]
            try:
                result = await handler(inputs)
                return ExecutionResult(output=str(result), status="completed")
            except Exception as e:
                return ExecutionResult(
                    output=f"Excepción durante la ejecución de la capacidad {cap.name}: {str(e)}",
                    status="failed",
                )

        # Despacho HTTP real (F1-T8)
        base_url = self._service_url_resolver(cap.provider_service)
        if not base_url:
            logger.warning(
                "Sin URL configurada para el provider_service; simulando ejecución",
                capability=cap.name, provider_service=cap.provider_service
            )
            return ExecutionResult(
                output=(
                    f"[Simulación] Capacidad '{cap.name}' ejecutada en servicio '{cap.provider_service}' "
                    f"vía '{cap.endpoint_path}' con parámetros: {inputs}. "
                    f"(No hay URL configurada para el servicio '{cap.provider_service}'.)"
                ),
                status="completed",
            )

        url = f"{base_url.rstrip('/')}{cap.endpoint_path}"
        correlation_id = get_correlation_id()
        headers = {"X-Correlation-Id": str(correlation_id)} if correlation_id else {}

        try:
            logger.info("Despachando capacidad real", capability=cap.name, url=url)
            # Las capacidades registradas hoy (ej. search_knowledge) exponen sus parámetros
            # como query params HTTP, no como body JSON.
            response = await self._http_client.post(url, params=inputs, headers=headers)
            response.raise_for_status()
            return ExecutionResult(output=response.text, status="completed")
        except Exception as e:
            logger.error("Fallo despachando capacidad real", capability=cap.name, url=url, error=str(e))
            return ExecutionResult(
                output=f"Excepción durante el despacho HTTP de '{cap.name}': {str(e)}",
                status="failed",
            )

    async def close(self) -> None:
        """Cierra el cliente HTTP interno."""
        await self._http_client.aclose()
