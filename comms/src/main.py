from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI, Header, HTTPException, status
from mindos_common.context import set_correlation_id
from mindos_common.event_bus import RedisEventBus
from mindos_common.ids import new_id
from mindos_common.logging import configure_logging, get_logger
from mindos_schemas.events.v1.communication_events import MessageSentEventData
from pydantic import BaseModel, Field

from comms.src.application.ports.communication import (
    CommunicationInboundPort,
    CommunicationOutboundPort,
)
from comms.src.config import settings
from comms.src.infrastructure.adapters.event_bus_inbound_handler import EventBusInboundHandler
from comms.src.infrastructure.adapters.whatsapp_outbound_adapter import WhatsAppOutboundAdapter

configure_logging("CommsService", settings.MINDOS_ENV)
logger = get_logger("comms_main")

app = FastAPI(
    title="MindOS Communication Service",
    description="Punto único de captura desde cualquier canal (F3-T3): CLI, REST, WhatsApp (F3-T4)",
    version="1.0.0",
)

# Bus de eventos (Redis Streams). La construcción es perezosa: no conecta hasta publicar.
event_bus = RedisEventBus(settings.REDIS_URL)
inbound_handler: CommunicationInboundPort = EventBusInboundHandler(event_bus, settings.INBOUND_STREAM)

# F3-T7: canales con entrega bidireccional real. CLI/REST no están aquí a propósito — son de
# solo-captura (F3-T3), no tienen una conexión persistente a la que entregarles una respuesta.
_outbound_http_client = httpx.AsyncClient(timeout=15.0)
outbound_channels: dict[str, CommunicationOutboundPort] = {
    "whatsapp": WhatsAppOutboundAdapter(_outbound_http_client, settings.WHATSAPP_URL),
}


class InboundMessageRequest(BaseModel):
    """Formato canónico de un mensaje entrante, sin importar el canal de origen."""
    provider: str = Field(..., description="Canal de origen: cli, rest, whatsapp, ...")
    sender_id: str = Field(..., description="Identificador del remitente en su canal (ej: número de teléfono)")
    recipient_id: str = Field(default="mindos", description="Identificador del destinatario (el bot/sistema)")
    text: str = Field(..., description="Contenido textual del mensaje")
    message_id: str | None = Field(default=None, description="ID del mensaje en el canal; se genera si falta")
    media_url: str | None = Field(default=None, description="URL de un archivo adjunto ya subido, si lo hay")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadatos crudos específicos del canal")


class InboundMessageResponse(BaseModel):
    status: str
    message_id: str
    provider: str


class OutboundMessageRequest(BaseModel):
    """F3-T7: una respuesta a entregar por el canal de origen del mensaje que la disparó."""
    provider: str = Field(..., description="Canal por el que entregar: whatsapp, cli, rest, ...")
    recipient_id: str = Field(..., description="Identificador del destinatario en su canal")
    text: str = Field(..., description="Contenido a entregar")
    message_id: str | None = Field(default=None, description="ID a asociar al envío; se genera si falta")


class OutboundMessageResponse(BaseModel):
    status: str
    message_id: str
    provider: str
    delivered: bool = Field(..., description="Si el canal soporta entrega bidireccional y esta tuvo éxito")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "comms", "env": settings.MINDOS_ENV}


@app.post("/api/v1/comms/inbound", status_code=status.HTTP_201_CREATED, response_model=InboundMessageResponse)
async def receive_inbound_message(
    request: InboundMessageRequest,
    x_correlation_id: UUID | None = Header(default=None, alias="X-Correlation-Id"),
):
    """
    F3-T3: entrada única de captura. CLI y REST (y WhatsApp en F3-T4) llaman exactamente este
    endpoint con el mismo formato — "capturar por CLI y por REST produce el mismo evento" no
    es una coincidencia de implementación, es la misma llamada a `inbound_handler.receive`.

    A diferencia del `publish_event` best-effort de Memory (que tiene un `event_log` durable en
    Postgres como respaldo), aquí el propio evento en el bus ES el único registro del mensaje —
    si Redis no responde, se falla de forma explícita (503) en vez de reportar éxito y perder el
    mensaje en silencio.
    """
    correlation_id = x_correlation_id or new_id()
    set_correlation_id(correlation_id)
    message_id = request.message_id or str(new_id())

    try:
        await inbound_handler.receive(
            provider=request.provider, sender_id=request.sender_id, recipient_id=request.recipient_id,
            text=request.text, message_id=message_id, media_url=request.media_url, metadata=request.metadata,
        )
    except Exception as e:
        logger.error("No se pudo capturar el mensaje entrante", provider=request.provider, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo capturar el mensaje (event bus no disponible). Intenta de nuevo.",
        ) from e

    return InboundMessageResponse(status="received", message_id=message_id, provider=request.provider)


@app.post("/api/v1/comms/outbound", status_code=status.HTTP_201_CREATED, response_model=OutboundMessageResponse)
async def send_outbound_message(
    request: OutboundMessageRequest,
    x_correlation_id: UUID | None = Header(default=None, alias="X-Correlation-Id"),
):
    """
    F3-T7: entrega una respuesta por el canal de origen — el agente (o Memory) la llama cuando
    un episodio con `reply_to` concluye, o cuando una capacidad queda pendiente de aprobación.

    A diferencia de `/inbound` (donde el evento en el bus ES el único registro), aquí la
    ENTREGA real es lo esencial — si el canal no soporta entrega bidireccional (cli/rest, F3-T3)
    o falla, se registra igual como evento (auditoría best-effort) pero no se trata como error:
    quien llama ya tiene su resultado, perder la notificación de "por si acaso" no debe fallar
    la respuesta al usuario que sí espera por HTTP.
    """
    correlation_id = x_correlation_id or new_id()
    set_correlation_id(correlation_id)
    message_id = request.message_id or str(new_id())

    channel = outbound_channels.get(request.provider)
    delivered = False
    status_label = "no_channel"
    if channel:
        try:
            await channel.send(request.recipient_id, request.text)
            delivered = True
            status_label = "sent"
        except Exception as e:
            logger.error("No se pudo entregar el mensaje saliente", provider=request.provider, error=str(e))
            status_label = "failed"
    else:
        logger.info(
            "Canal sin entrega bidireccional, se omite el envío", provider=request.provider,
        )

    try:
        event_data = MessageSentEventData(
            message_id=message_id, recipient_id=request.recipient_id, provider=request.provider,
            text=request.text, status=status_label,
        )
        await event_bus.publish(
            settings.OUTBOUND_STREAM, "com.mindos.communication.message.sent", event_data, correlation_id,
        )
    except Exception as e:
        logger.warning("No se pudo publicar el evento de mensaje saliente", error=str(e))

    return OutboundMessageResponse(
        status=status_label, message_id=message_id, provider=request.provider, delivered=delivered,
    )

# Fin del módulo main
