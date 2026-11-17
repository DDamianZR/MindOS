import asyncio
from collections.abc import AsyncIterator
from typing import Any

import anthropic
from mindos_common.logging import get_logger

from agents.src.application.assistant.system_prompt import BASE_SYSTEM_PROMPT, conversation_context
from agents.src.application.assistant.toolbox import AssistantToolbox, ToolOutcome
from agents.src.application.ports.personal_agent import (
    AgentEvent,
    Conversation,
    PersonalAgentPort,
    TextDelta,
    ThinkingDelta,
    ToolFinished,
    ToolStarted,
    TurnFailed,
    TurnFinished,
    TurnRestarted,
)

logger = get_logger("claude_personal_agent")

FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Bloques que no se reenvían si aparecen ANTES del último bloque `fallback` de un turno: los
# produjo el modelo que declinó a mitad de respuesta y el modelo de relevo no puede leerlos.
_DROPPED_BEFORE_FALLBACK = {"thinking", "redacted_thinking", "tool_use"}
_MAX_JSON_RETRIES = 2


def _echoable_content(content: list[Any]) -> list[Any]:
    """Contenido de un turno del asistente tal como debe reenviarse en la siguiente petición."""
    last_fallback = max((i for i, block in enumerate(content) if block.type == "fallback"), default=-1)
    if last_fallback < 0:
        return list(content)
    return [
        block for i, block in enumerate(content)
        if i >= last_fallback or block.type not in _DROPPED_BEFORE_FALLBACK
    ]


def _friendly_error(error: Exception) -> str:
    """Mensaje para la persona, de la excepción más específica a la más general."""
    if isinstance(error, anthropic.AuthenticationError):
        return "La API key de Claude no es válida. Revisa ANTHROPIC_API_KEY en el archivo .env del servicio."
    if isinstance(error, anthropic.PermissionDeniedError):
        return "La API key de Claude no tiene permiso para usar este modelo."
    if isinstance(error, anthropic.NotFoundError):
        return "El modelo configurado en ANTHROPIC_MODEL no existe o no está disponible para esta cuenta."
    if isinstance(error, anthropic.RateLimitError):
        return "Claude está limitando las peticiones en este momento. Espera unos segundos y vuelve a intentarlo."
    if isinstance(error, anthropic.BadRequestError):
        return f"Claude rechazó la petición: {error.message}"
    if isinstance(error, anthropic.APIStatusError):
        if error.status_code >= 500:
            return "Claude tuvo un problema temporal. Vuelve a intentarlo en un momento."
        return f"Error de la API de Claude ({error.status_code}): {error.message}"
    if isinstance(error, anthropic.APIConnectionError):
        return "No se pudo conectar con la API de Claude. Revisa la conexión a internet del servidor."
    if isinstance(error, anthropic.AnthropicError):
        # Típicamente: no hay ninguna credencial configurada (el SDK lo detecta al enviar).
        return f"El cliente de Claude no está bien configurado: {error}"
    return "Ocurrió un error inesperado al generar la respuesta."


class ClaudePersonalAgent(PersonalAgentPort):
    """
    Asistente personal sobre la API de Claude (F7-T3): bucle manual de herramientas con
    streaming token a token.

    Decisiones que dependen del modelo (Claude Sonnet 5.5):
    - El razonamiento es adaptativo y siempre activo; la profundidad se controla con `effort`.
      `display: "summarized"` devuelve resúmenes legibles y las notas de progreso que el modelo
      escribe entre herramientas, que la interfaz muestra como estado.
    - `tool_choice` se queda en `auto` (forzar una herramienta devuelve 400 en este modelo).
    - El historial es solo-anexar y los bloques de razonamiento se reenvían sin tocar: el
      proveedor valida que `system`, `tools` y los mensajes previos no hayan cambiado.
    - El caché de prompt cubre herramientas + prompt base (estables entre conversaciones) y,
      con el `cache_control` de nivel superior, el historial de la conversación en curso.
    """

    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        toolbox: AssistantToolbox,
        model: str = "claude-sonnet-5-5",
        effort: str = "low",
        max_tokens: int = 16000,
        max_tool_rounds: int = 10,
        fallbacks_enabled: bool = True,
        owner_name: str = "",
    ):
        self._client = client
        self._toolbox = toolbox
        self._model = model
        self._effort = effort
        self._max_tokens = max_tokens
        self._max_tool_rounds = max_tool_rounds
        self._fallbacks_enabled = fallbacks_enabled
        self._owner_name = owner_name
        self._tools = [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema,
                # Las entradas llegan según se generan (una nota larga no deja el stream mudo).
                # A cambio el servidor deja de validarlas: lo hace `AssistantToolbox.execute`.
                "eager_input_streaming": True,
            }
            for spec in toolbox.specs
        ]

    @property
    def model_name(self) -> str:
        return self._model

    def _request_params(self, conversation: Conversation) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": [
                {"type": "text", "text": BASE_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": conversation_context(conversation.started_at, self._owner_name)},
            ],
            "tools": self._tools,
            "messages": conversation.messages,
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": self._effort},
            "cache_control": {"type": "ephemeral"},
        }
        if self._fallbacks_enabled:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    async def stream_reply(self, conversation: Conversation, user_text: str) -> AsyncIterator[AgentEvent]:
        checkpoint = len(conversation.messages)
        conversation.messages.append({"role": "user", "content": user_text})
        usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        answer_parts: list[str] = []
        tools_used: list[dict[str, Any]] = []
        served_by = self._model
        json_retries = 0
        rounds = 0
        settled = False  # True cuando el turno terminó bien o ya se deshizo explícitamente

        def rollback() -> None:
            nonlocal settled
            settled = True
            del conversation.messages[checkpoint:]

        def finish(stop_reason: str) -> TurnFinished:
            nonlocal settled
            settled = True
            conversation.transcript.append({"role": "user", "text": user_text})
            conversation.transcript.append({
                "role": "assistant", "text": "".join(answer_parts), "tools": tools_used,
                "stop_reason": stop_reason,
            })
            return TurnFinished(stop_reason=stop_reason, model=served_by, usage=usage)

        try:
            while True:
                round_text: list[str] = []
                try:
                    async with self._client.beta.messages.stream(**self._request_params(conversation)) as stream:
                        async for event in stream:
                            if event.type != "content_block_delta":
                                continue
                            if event.delta.type == "text_delta":
                                round_text.append(event.delta.text)
                                yield TextDelta(event.delta.text)
                            elif event.delta.type == "thinking_delta" and event.delta.thinking:
                                yield ThinkingDelta(event.delta.thinking)
                        message = await stream.get_final_message()
                    json_retries = 0
                except ValueError:
                    # JSON de entrada de herramienta que el SDK no pudo interpretar. Falló antes de
                    # cerrar el bloque `tool_use`, así que no hay nada que responder: se reintenta
                    # el turno (acotado). Los errores de la API no son ValueError y siguen abajo.
                    json_retries += 1
                    if json_retries > _MAX_JSON_RETRIES:
                        rollback()
                        yield TurnFailed("El modelo generó una llamada a herramienta ilegible varias veces seguidas.")
                        return
                    yield TurnRestarted()
                    continue
                except anthropic.AnthropicError as e:
                    logger.error("Fallo llamando a la API de Claude", error=str(e), error_type=type(e).__name__)
                    rollback()
                    yield TurnFailed(_friendly_error(e))
                    return

                served_by = message.model or served_by
                for key in usage:
                    usage[key] += getattr(message.usage, key, None) or 0

                if message.stop_reason == "refusal":
                    # No se conserva el turno declinado: la conversación sigue desde el último punto sano.
                    rollback()
                    category = getattr(message.stop_details, "category", None) if message.stop_details else None
                    logger.warning("Claude declinó la petición", category=category)
                    yield TurnFailed(
                        "Claude declinó responder a este mensaje por sus políticas de uso. "
                        "Prueba a reformularlo."
                    )
                    return

                content = _echoable_content(message.content)
                answer_parts.extend(round_text)
                tool_uses = [block for block in content if block.type == "tool_use"]

                if message.stop_reason == "pause_turn":
                    conversation.messages.append({"role": "assistant", "content": content})
                    continue

                if not tool_uses:
                    conversation.messages.append({"role": "assistant", "content": content})
                    yield finish(message.stop_reason or "end_turn")
                    return

                if message.stop_reason == "max_tokens":
                    # Una entrada de herramienta truncada se parsea como un objeto parcial válido: no se ejecuta.
                    rollback()
                    yield TurnFailed(
                        "La respuesta se cortó a mitad de una acción por el límite de tokens. "
                        "Sube ASSISTANT_MAX_TOKENS o pide algo más acotado."
                    )
                    return

                if rounds >= self._max_tool_rounds:
                    rollback()
                    yield TurnFailed(
                        "El asistente no llegó a una respuesta tras demasiadas consultas seguidas. "
                        "Intenta con una pregunta más concreta."
                    )
                    return
                rounds += 1

                for block in tool_uses:
                    spec = self._toolbox.resolve(block.name)
                    yield ToolStarted(
                        id=block.id, name=block.name, label=spec.label if spec else block.name,
                        input=block.input if isinstance(block.input, dict) else {},
                    )

                outcomes: list[ToolOutcome] = await asyncio.gather(
                    *(self._toolbox.execute(block.name, block.input) for block in tool_uses)
                )

                tool_results = []
                for block, outcome in zip(tool_uses, outcomes, strict=True):
                    yield ToolFinished(
                        id=block.id, name=block.name, ok=not outcome.is_error,
                        summary=outcome.summary, sources=outcome.sources,
                    )
                    tools_used.append({
                        "id": block.id, "name": block.name, "ok": not outcome.is_error,
                        "summary": outcome.summary, "sources": outcome.sources,
                    })
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": block.id,
                        "content": outcome.content, "is_error": outcome.is_error,
                    })

                # Todas las respuestas en un único mensaje de usuario: repartirlas en varios enseña
                # al modelo a dejar de llamar herramientas en paralelo.
                conversation.messages.append({"role": "assistant", "content": content})
                conversation.messages.append({"role": "user", "content": tool_results})
        finally:
            # El cliente cortó la conexión (o algo inesperado interrumpió el generador) a mitad
            # de turno: se deshace para que el historial nunca quede con un turno a medias.
            if not settled:
                del conversation.messages[checkpoint:]
