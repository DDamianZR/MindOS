from typing import Any
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, status
from mindos_common.context import set_correlation_id
from mindos_common.event_bus import RedisEventBus
from mindos_common.ids import new_id
from mindos_common.logging import configure_logging, get_logger
from pydantic import BaseModel, Field

from comms.src.application.ports.communication import CommunicationInboundPort
from comms.src.config import settings
from comms.src.infrastructure.adapters.event_bus_inbound_handler import EventBusInboundHandler

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

# Fin del módulo main
