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


class AssistantSourceDto(BaseModel):
    """
    Una fuente que respalda una respuesta. `kind="memory"` lleva `node_id` (un nodo de la
    memoria); `kind="web"` lleva `url` (una página leída con las herramientas web de Claude).
    """
    kind: Literal["memory", "web"] = "memory"
    title: str
    node_id: str | None = None
    url: str | None = None
    object_type: str | None = None
    score: float | None = None


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


class AssistantCountItem(BaseModel):
    key: str
    count: int


class AssistantUsageTotals(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


class AssistantDayCount(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD (UTC)")
    turns: int


class AssistantStatsResponse(BaseModel):
    """
    `GET /api/v1/agents/assistant/stats` (Fase 8): uso del asistente desde que arrancó el
    servicio de agentes (en memoria del proceso; se reinicia con él).
    """
    provider: Literal["anthropic", "demo"]
    model: str
    since: str = Field(..., description="ISO 8601 del arranque del registro")
    conversations: int
    turns: int
    failed_turns: int
    tool_calls: list[AssistantCountItem] = Field(default_factory=list, description="Por herramienta, de mayor a menor")
    usage: AssistantUsageTotals
    cache_hit_ratio: float | None = Field(
        default=None,
        description="cache_read / (input + cache_read + cache_creation); nulo si no hubo tokens",
    )
    estimated_cost_usd: float = Field(..., description="Según ASSISTANT_PRICING de config; 0 en demo")
    avg_turn_seconds: float | None = None
    turns_by_day: list[AssistantDayCount] = Field(
        default_factory=list, description="Últimos 14 días incluido hoy, uno por día aunque sea cero, ascendente"
    )
