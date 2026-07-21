from datetime import datetime, timezone
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

# Definimos un TypeVar para los datos específicos de cada tipo de evento
T = TypeVar('T', bound=BaseModel)

class CloudEvent(BaseModel, Generic[T]):
    """
    Especificación de evento base de MindOS compatible con el estándar CloudEvents v1.0.
    """
    specversion: str = Field(default="1.0", description="Versión de la especificación de CloudEvents")
    id: UUID = Field(..., description="Identificador único del evento. Se debe usar obligatoriamente UUIDv7.")
    source: str = Field(
        ...,
        description="Identifica el contexto o microservicio en el que ocurrió el evento (ej: '/services/whatsapp')"
    )
    type: str = Field(
        ...,
        description="Tipo de evento estructurado con namespace (ej: com.mindos.communication.message.received)"
    )
    time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp del momento en que ocurrió el evento en UTC"
    )
    datacontenttype: str = Field(default="application/json", description="Tipo de contenido de los datos serializados")
    data: T = Field(..., description="Payload específico del evento")
    correlation_id: UUID = Field(
        ...,
        description="ID de correlación (UUIDv7) para trazabilidad (tracing) inter-servicios"
    )
