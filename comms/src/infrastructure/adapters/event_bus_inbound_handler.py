from typing import Any

from mindos_common.context import get_correlation_id
from mindos_common.ids import new_id
from mindos_common.logging import get_logger
from mindos_schemas.events.v1.communication_events import MessageReceivedEventData

from comms.src.application.ports.communication import CommunicationInboundPort

logger = get_logger("event_bus_inbound_handler")


class EventBusInboundHandler(CommunicationInboundPort):
    """
    Implementación real de `CommunicationInboundPort` (F3-T3): publica un
    `com.mindos.communication.message.received` en el Event Bus por cada mensaje entrante,
    sin importar el canal que lo originó. El pipeline de ingestión (F3-T5) lo consume.
    """
    def __init__(self, event_bus, stream_name: str):
        self.event_bus = event_bus
        self.stream_name = stream_name

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
        event_data = MessageReceivedEventData(
            message_id=message_id, sender_id=sender_id, recipient_id=recipient_id,
            provider=provider, text=text, media_url=media_url, metadata=metadata or {},
        )
        correlation_id = get_correlation_id() or new_id()
        await self.event_bus.publish(
            self.stream_name, "com.mindos.communication.message.received", event_data, correlation_id
        )
        logger.info(
            "Mensaje entrante publicado", provider=provider, message_id=message_id,
            correlation_id=str(correlation_id),
        )
        return message_id
