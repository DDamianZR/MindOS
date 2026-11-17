# DTOs API v1 — asistente personal (Fase 7)
from typing import Any, Literal

from pydantic import BaseModel, Field


class AssistantChatRequest(BaseModel):
    """Un mensaje de la persona al asistente personal (F7-T4). La respuesta es un stream SSE."""
    message: str = Field(..., min_length=1, max_length=50_000, description="Texto del mensaje")
    conversation_id: str | None = Field(
        default=None,
        description="Conversación a continuar. Nulo abre una nueva; su ID llega en el primer evento del stream.",
    )


class AssistantStatusResponse(BaseModel):
    """Qué hay detrás del asistente ahora mismo, para que la interfaz lo muestre sin adivinar."""
    provider: Literal["anthropic", "demo"] = Field(
        ..., description="'anthropic' = Claude real; 'demo' = respuestas guionizadas sin API key"
    )
    model: str = Field(..., description="Identificador del modelo que responde")
    tools: list[str] = Field(default_factory=list, description="Herramientas disponibles para el asistente")


class AssistantToolUseDto(BaseModel):
    """Una herramienta usada durante un turno, con las fuentes que consultó."""
    id: str
    name: str
    ok: bool
    summary: str = ""
    sources: list[dict[str, Any]] = Field(default_factory=list)


class AssistantTranscriptMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    tools: list[AssistantToolUseDto] = Field(default_factory=list)
    stop_reason: str | None = None


class AssistantConversationResponse(BaseModel):
    """Transcripción de una conversación, para restaurarla al recargar la interfaz."""
    conversation_id: str
    started_at: str
    messages: list[AssistantTranscriptMessage]
