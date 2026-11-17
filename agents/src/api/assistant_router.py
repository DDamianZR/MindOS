"""
Asistente personal (F7-T4): conversación en streaming con la memoria de MindOS.

`POST /chat` responde con Server-Sent Events. Cada evento lleva en `event:` el tipo y en `data:`
un JSON. Orden de un turno: `conversation` (una vez, con el ID), luego cualquier mezcla de
`thinking` / `text` / `tool_start` / `tool_end` / `restart`, y siempre un cierre: `done` o `error`.
"""
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from mindos_common.logging import get_logger
from mindos_schemas.api.v1.assistant_dto import (
    AssistantChatRequest,
    AssistantConversationResponse,
    AssistantStatusResponse,
)

from agents.src.application.assistant.toolbox import TOOL_SPECS
from agents.src.application.ports.conversation_store import ConversationStorePort
from agents.src.application.ports.personal_agent import PersonalAgentPort, event_to_dict
from agents.src.main import get_conversation_store, get_personal_agent

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
        try:
            yield _sse("conversation", {"conversation_id": conversation.id})
            async for event in agent.stream_reply(conversation, request.message):
                yield _sse(event.type, event_to_dict(event))
        except Exception as e:  # el stream ya empezó: el error solo puede viajar como evento
            logger.error("Error inesperado en el stream del asistente", error=str(e), error_type=type(e).__name__)
            yield _sse("error", {"type": "error", "message": "Ocurrió un error inesperado al generar la respuesta."})
        finally:
            _busy_conversations.discard(conversation.id)

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
