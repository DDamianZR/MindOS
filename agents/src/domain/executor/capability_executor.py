from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import httpx
from mindos_common.context import get_correlation_id
from mindos_common.ids import new_id
from mindos_common.logging import get_logger
from mindos_schemas.api.v1.agent_dto import PlanStep
from mindos_schemas.capabilities import Capability

from agents.src.application.ports.approval import ApprovalPort
from agents.src.application.registry.capability_registry_port import CapabilityRegistryPort
from agents.src.domain.executor.executor import ExecutionResult, Executor
from agents.src.infrastructure.adapters.in_memory_approval_store import InMemoryApprovalStore

logger = get_logger("capability_executor")

ServiceUrlResolver = Callable[[str], str | None]


class CapabilityExecutor(Executor):
    """
    Implementación concreta de Executor que despacha la ejecución utilizando el
    CapabilityRegistry para determinar el destino y formato de la llamada.

    Si la capacidad tiene un handler mock registrado (solo para tests), lo usa. Si no, y el
    `provider_service` resuelve a una URL conocida, hace un despacho HTTP real (F1-T8).
    Si la capacidad exige `requires_approval`, la ejecución se pausa y se persiste un
    `ApprovalRequest` (F3-T1/F3-T7) con todo lo necesario para despacharla más tarde, sin
    despachar nada todavía.
    """
    def __init__(
        self,
        registry: CapabilityRegistryPort,
        service_url_resolver: ServiceUrlResolver | None = None,
        http_client: httpx.AsyncClient | None = None,
        approval_store: ApprovalPort | None = None,
        comms_url: str | None = None,
    ):
        self.registry = registry
        self._mock_handlers: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {}
        self._service_url_resolver = service_url_resolver or (lambda _service: None)
        self._http_client = http_client or httpx.AsyncClient(timeout=15.0)
        self.approval_store = approval_store or InMemoryApprovalStore()
        # F3-T7: si se da y el paso tiene `reply_to`, notifica por el canal de origen que una
        # aprobación quedó pendiente. None (default) preserva el comportamiento de F1-T8/F3-T1
        # (pausar sin notificar) para quien construya el executor sin conocer comms/.
        self.comms_url = comms_url.rstrip("/") if comms_url else None

    def register_mock_handler(self, capability_name: str, handler_callable) -> None:
        """Permite registrar un mock ejecutable en memoria. Uso exclusivo de tests/simulación."""
        self._mock_handlers[capability_name] = handler_callable

    async def execute_step(
        self,
        step: PlanStep,
        inputs: dict[str, Any],
        episode_id: UUID,
        reply_to: dict[str, str] | None = None,
    ) -> ExecutionResult:
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
        # humano. La resolución de la aprobación llega vía Gateway (F3-T1/F3-T7).
        if cap.requires_approval:
            approval_id = new_id()
            await self.approval_store.create(
                approval_id=approval_id, episode_id=episode_id, step_id=step.step_id,
                capability_name=cap.name, inputs=inputs, reply_to=reply_to,
            )
            logger.warning(
                "Capacidad requiere aprobación humana, ejecución pausada",
                capability=cap.name, step_id=step.step_id, approval_id=str(approval_id),
            )
            if reply_to:
                await self._notify_approval_needed(approval_id, cap.name, reply_to)
            return ExecutionResult(
                output=(
                    f"La capacidad '{cap.name}' requiere aprobación humana antes de ejecutarse. "
                    f"approval_id={approval_id}"
                ),
                status="pending_approval",
            )

        return await self._dispatch(cap, inputs)

    async def _notify_approval_needed(
        self, approval_id: UUID, capability_name: str, reply_to: dict[str, str]
    ) -> None:
        """F3-T7: "una acción sensible pregunta al usuario por WhatsApp... y solo procede tras
        el sí" — best-effort, igual que el resto de la mensajería saliente: perder el aviso no
        debe tumbar la ejecución del agente (el approval sigue creado y resoluble por API)."""
        if not self.comms_url:
            return
        text = (
            f"MindOS necesita tu aprobación para ejecutar '{capability_name}'. "
            f"ID de la solicitud: {approval_id}"
        )
        try:
            resp = await self._http_client.post(f"{self.comms_url}/api/v1/comms/outbound", json={
                "provider": reply_to["provider"], "recipient_id": reply_to["sender_id"], "text": text,
            })
            resp.raise_for_status()
        except Exception as e:
            logger.warning("No se pudo notificar la aprobación pendiente", approval_id=str(approval_id), error=str(e))

    async def execute_capability_by_name(self, capability_name: str, inputs: dict[str, Any]) -> ExecutionResult:
        """
        Despacha una capacidad por nombre sin un `PlanStep` (F3-T7): usado al resolver una
        aprobación, donde ya no hay un plan en curso, solo lo persistido en el `ApprovalRequest`.
        """
        cap = await self.registry.get_by_name(capability_name)
        if not cap:
            return ExecutionResult(
                output=f"Error: La capacidad '{capability_name}' ya no está registrada en el ecosistema.",
                status="failed",
            )
        return await self._dispatch(cap, inputs)

    async def _dispatch(self, cap: Capability, inputs: dict[str, Any]) -> ExecutionResult:
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
