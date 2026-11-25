"""
Asistente personal (F7-T4): conversación en streaming con la memoria de MindOS.

`POST /chat` responde con Server-Sent Events. Cada evento lleva en `event:` el tipo y en `data:`
un JSON. Orden de un turno: `conversation` (una vez, con el ID), luego cualquier mezcla de
`thinking` / `text` / `tool_start` / `tool_end` / `restart`, y siempre un cierre: `done` o `error`.
"""
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from mindos_common.logging import get_logger
from mindos_schemas.api.v1.assistant_dto import (
    AssistantChatRequest,
    AssistantConversationResponse,
    AssistantCountItem,
    AssistantDayCount,
    AssistantStatsResponse,
    AssistantStatusResponse,
    AssistantUsageTotals,
)

from agents.src.application.assistant.toolbox import TOOL_SPECS
from agents.src.application.ports.conversation_store import ConversationStorePort
from agents.src.application.ports.personal_agent import (
    PersonalAgentPort,
    ToolFinished,
    TurnFinished,
    event_to_dict,
)
from agents.src.application.ports.usage_recorder import UsageRecorderPort
from agents.src.main import get_conversation_store, get_personal_agent, get_usage_recorder

logger = get_logger("assistant_router")

router = APIRouter(prefix="/api/v1/agents/assistant", tags=["assistant"])

# Conversaciones con un turno en curso. El historial es solo-anexar y un segundo turno
# simultáneo lo intercalaría; con un solo proceso basta un conjunto en memoria.
_busy_conversations: set[str] = set()


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/status", response_model=AssistantStatusResponse)
async def assistant_status(agent: PersonalAgentPort = Depends(get_personal_agent)):
    return AssistantStatusResponse(
        provider="demo" if agent.model_name == "demo" else "anthropic",
        model=agent.model_name,
        tools=[spec.name for spec in TOOL_SPECS],
    )


@router.post("/chat")
async def assistant_chat(
    request: AssistantChatRequest,
    agent: PersonalAgentPort = Depends(get_personal_agent),
    store: ConversationStorePort = Depends(get_conversation_store),
    recorder: UsageRecorderPort = Depends(get_usage_recorder),
):
    if request.conversation_id:
        conversation = await store.get(request.conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Esa conversación ya no existe (el servicio se reinició). Empieza una nueva.",
            )
    else:
        conversation = await store.create()

    if conversation.id in _busy_conversations:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El asistente todavía está respondiendo el mensaje anterior de esta conversación.",
        )

    async def event_stream() -> AsyncIterator[str]:
        # Se marca aquí y no antes de devolver la respuesta: si el cliente se va antes de que el
        # stream arranque, este generador nunca corre y su `finally` tampoco.
        _busy_conversations.add(conversation.id)
        started = time.perf_counter()
        tools: list[str] = []
        usage: dict[str, int] = {}
        ok = False
        try:
            yield _sse("conversation", {"conversation_id": conversation.id})
            async for event in agent.stream_reply(conversation, request.message):
                if isinstance(event, ToolFinished):
                    tools.append(event.name)
                elif isinstance(event, TurnFinished):
                    ok = True
                    usage = dict(event.usage)
                yield _sse(event.type, event_to_dict(event))
        except Exception as e:  # el stream ya empezó: el error solo puede viajar como evento
            logger.error("Error inesperado en el stream del asistente", error=str(e), error_type=type(e).__name__)
            yield _sse("error", {"type": "error", "message": "Ocurrió un error inesperado al generar la respuesta."})
        finally:
            # Primero se suelta la conversación: anotar el uso no puede dejar el chat bloqueado.
            # El `finally` (y no solo el evento `done`) hace que un turno que termina en error
            # también cuente, y que se anote una sola vez.
            _busy_conversations.discard(conversation.id)
            # Se guarda siempre, también si el turno falló o el cliente se fue: el agente ya dejó
            # el historial consistente (rollback), y así no se pierde la conversación previa.
            try:
                await store.save(conversation)
            except Exception as e:
                logger.error("No se pudo guardar la conversación", error=str(e), error_type=type(e).__name__)
            await recorder.record_turn(
                conversation.id,
                ok=ok,
                duration_seconds=time.perf_counter() - started,
                tools=tools,
                usage=usage,
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        # `X-Accel-Buffering: no` evita que un proxy intermedio retenga los eventos.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations/{conversation_id}", response_model=AssistantConversationResponse)
async def get_conversation(
    conversation_id: str,
    store: ConversationStorePort = Depends(get_conversation_store),
):
    conversation = await store.get(conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada.")
    return AssistantConversationResponse(
        conversation_id=conversation.id,
        started_at=conversation.started_at,
        messages=conversation.transcript,
    )


@router.get("/stats", response_model=AssistantStatsResponse)
async def assistant_stats(
    agent: PersonalAgentPort = Depends(get_personal_agent),
    recorder: UsageRecorderPort = Depends(get_usage_recorder),
):
    snap = await recorder.snapshot(agent.model_name)
    return AssistantStatsResponse(
        provider="demo" if agent.model_name == "demo" else "anthropic",
        model=agent.model_name,
        since=snap.since,
        conversations=snap.conversations,
        turns=snap.turns,
        failed_turns=snap.failed_turns,
        tool_calls=[AssistantCountItem(key=item.key, count=item.count) for item in snap.tool_calls],
        usage=AssistantUsageTotals(
            input_tokens=snap.usage.input_tokens,
            output_tokens=snap.usage.output_tokens,
            cache_read_input_tokens=snap.usage.cache_read_input_tokens,
            cache_creation_input_tokens=snap.usage.cache_creation_input_tokens,
        ),
        cache_hit_ratio=snap.cache_hit_ratio,
        estimated_cost_usd=snap.estimated_cost_usd,
        avg_turn_seconds=snap.avg_turn_seconds,
        turns_by_day=[AssistantDayCount(date=day.date, turns=day.turns) for day in snap.turns_by_day],
    )
