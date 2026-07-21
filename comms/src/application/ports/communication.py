from abc import ABC, abstractmethod
from typing import Any


class CommunicationInboundPort(ABC):
    """
    Puerto de entrada (F3-T3): procesa un mensaje recibido de CUALQUIER canal (CLI, REST,
    WhatsApp...). Cada adaptador de canal traduce su formato nativo a estos mismos parámetros
    y llama a `receive` — así "capturar por CLI y por REST produce el mismo evento" (DoD) no es
    una coincidencia de implementación, es la misma llamada.
    """
    @abstractmethod
    async def receive(
        self,
        provider: str,
        sender_id: str,
        recipient_id: str,
        text: str,
        message_id: str,
        media_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Procesa el mensaje entrante (típicamente publicándolo al Event Bus) y retorna su `message_id`."""
        pass


class CommunicationOutboundPort(ABC):
    """
    Puerto de salida (F3-T3/F3-T7): entrega un mensaje saliente por un canal específico.
    Cada canal bidireccional (WhatsApp en F3-T4) implementa el suyo; canales de solo-captura
    (CLI/REST) no tienen una noción útil de "entregar después" y no requieren implementarlo.
    """
    @abstractmethod
    async def send(self, recipient_id: str, text: str) -> dict[str, Any]:
        """Envía `text` a `recipient_id` por este canal. Retorna detalles de entrega (status, etc.)."""
        pass
