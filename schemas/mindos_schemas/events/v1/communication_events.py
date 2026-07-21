from typing import Any

from pydantic import BaseModel, Field


class MessageReceivedEventData(BaseModel):
    """
    Payload de datos para el evento com.mindos.communication.message.received
    """
    message_id: str = Field(..., description="ID único del mensaje provisto por la plataforma emisora")
    sender_id: str = Field(..., description="Identificador único del remitente (ej: número de teléfono o ID de chat)")
    recipient_id: str = Field(..., description="Identificador del destinatario (ej: número del bot o usuario receptor)")
    provider: str = Field(..., description="Nombre del canal/proveedor (ej: whatsapp, telegram, signal, cli)")
    text: str = Field(..., description="Contenido textual del mensaje")
    media_url: str | None = Field(default=None, description="URL de archivos multimedia asociados si existen")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos específicos del canal/proveedor en crudo"
    )


class MessageSentEventData(BaseModel):
    """
    Payload de datos para el evento com.mindos.communication.message.sent
    """
    message_id: str = Field(..., description="ID de mensaje generado por la capa de comunicación")
    recipient_id: str = Field(..., description="Identificador único del destinatario")
    provider: str = Field(..., description="Proveedor por el cual se envió el mensaje")
    text: str = Field(..., description="Contenido enviado")
    status: str = Field(..., description="Estado de la entrega (ej: sent, delivered, failed)")
    error_message: str | None = Field(default=None, description="Detalles del error si falló el envío")
