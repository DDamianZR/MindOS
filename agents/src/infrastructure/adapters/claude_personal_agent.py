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
# Las ejecuta Claude en sus servidores: no llevan `input_schema` ni se responden con `tool_result`.
_SERVER_WEB_TOOLS = (
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5},
)
_WEB_TOOL_LABELS = {
    "web_search": "Buscando en la web",
    "web_fetch": "Leyendo una página",
}
_WEB_RESULT_NAMES = {
    "web_search_tool_result": "web_search",
    "web_fetch_tool_result": "web_fetch",
}
_WEB_ERROR_SUMMARIES = {
    "invalid_tool_input": "No se pudo consultar la web con esos datos.",
    "unavailable": "La web no está disponible en este momento.",
    "max_uses_exceeded": "Se alcanzó el límite de consultas a la web en este turno.",
    "too_many_requests": "Hay demasiadas consultas a la web. Prueba de nuevo en un momento.",
    "query_too_long": "La consulta es demasiado larga.",
    "request_too_large": "La consulta es demasiado grande.",
    "url_too_long": "La dirección de la página es demasiado larga.",
    "url_not_allowed": "Esa página no se puede leer.",
    "url_not_in_prior_context": "Esa página no salió de la búsqueda.",
    "url_not_accessible": "No se pudo abrir esa página.",
    "unsupported_content_type": "El contenido de esa página no se puede leer.",
    "content_too_large": "La página es demasiado grande para leerla.",
}


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


def _field(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _web_source(title: Any, url: Any) -> dict[str, Any]:
    return {
        "kind": "web",
        "title": str(title) if title else (str(url) if url else "Página web"),
        "url": url if isinstance(url, str) else None,
        "node_id": None,
        "object_type": None,
        "score": None,
    }


def _input_ready(name: str, tool_input: dict[str, Any]) -> bool:
    """La consulta o la URL ya están completas; un objeto vacío es el arranque del bloque."""
    if name == "web_search":
        return bool(tool_input.get("query"))
    if name == "web_fetch":
        return bool(tool_input.get("url"))
    return bool(tool_input)


def _tool_started(block: Any) -> ToolStarted:
    name = str(_field(block, "name") or "")
    tool_input = _field(block, "input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    return ToolStarted(
        id=str(_field(block, "id") or ""),
        name=name,
        label=_WEB_TOOL_LABELS.get(name, name),
        input=dict(tool_input),
    )


def _started_if_ready(block: Any) -> ToolStarted | None:
    if _field(block, "type") != "server_tool_use":
        return None
    tool_input = _field(block, "input")
    if not isinstance(tool_input, dict) or not _input_ready(str(_field(block, "name") or ""), tool_input):
        return None
    return _tool_started(block)


def _web_error_code(content: Any) -> str | None:
    """Un fallo llega como objeto; un acierto de búsqueda, como lista. No se recorre el objeto."""
    if content is None or isinstance(content, list):
        return None
    type_ = _field(content, "type")
    if type_ in {"web_search_tool_result_error", "web_fetch_tool_result_error"}:
        return str(_field(content, "error_code") or "unavailable")
    if type_ == "web_fetch_result":
        return None
    code = _field(content, "error_code")
    return str(code) if code else None


def _web_error_summary(code: str | None) -> str:
    if code and code in _WEB_ERROR_SUMMARIES:
        return _WEB_ERROR_SUMMARIES[code]
    return "No se pudo consultar la web."


def _search_sources(content: list[Any]) -> list[dict[str, Any]]:
    sources = []
    for item in content:
        if _field(item, "type") != "web_search_result":
            continue
        sources.append(_web_source(_field(item, "title"), _field(item, "url")))
    return sources


def _fetch_source(content: Any) -> dict[str, Any]:
    url = _field(content, "url")
    document = _field(content, "document")
    if document is None:
        inner = _field(content, "content")
        if inner is not None and not isinstance(inner, (str, list, bytes)):
            document = inner
    title = _field(document, "title") if document is not None else None
    return _web_source(title, url)


def _finished_from_result(block: Any) -> ToolFinished:
    result_type = _field(block, "type")
    name = _WEB_RESULT_NAMES.get(result_type, "web_search")
    tool_id = str(_field(block, "tool_use_id") or _field(block, "id") or "")
    content = _field(block, "content")
    code = _web_error_code(content)
    if code is not None or (name == "web_search" and not isinstance(content, list)):
        return ToolFinished(id=tool_id, name=name, ok=False, summary=_web_error_summary(code), sources=[])
    if name == "web_fetch":
        return ToolFinished(id=tool_id, name=name, ok=True, summary="Página leída", sources=[_fetch_source(content)])
    sources = _search_sources(content)
    noun = "resultado" if len(sources) == 1 else "resultados"
    return ToolFinished(id=tool_id, name=name, ok=True, summary=f"{len(sources)} {noun}", sources=sources)


def _server_event_from_stream(event: Any) -> ToolStarted | ToolFinished | None:
    event_type = getattr(event, "type", None)
    if event_type == "content_block_start":
        block = getattr(event, "content_block", None)
        if _field(block, "type") in _WEB_RESULT_NAMES:
            return _finished_from_result(block)
        return _started_if_ready(block)
    if event_type == "content_block_stop":
        # El `input` se arma con los `input_json_delta`; al cerrar el bloque ya está completo.
        return _started_if_ready(getattr(event, "content_block", None))
    return None


def _deferred_server_event(
    block: Any, started_ids: set[str], finished_ids: set[str],
) -> ToolStarted | ToolFinished | None:
    """Lo que el stream no pudo emitir porque el `input` solo estaba en el mensaje final."""
    block_type = _field(block, "type")
    if block_type == "server_tool_use":
        tool_id = str(_field(block, "id") or "")
        if tool_id in started_ids:
            return None
        return _tool_started(block)
    if block_type in _WEB_RESULT_NAMES:
        finished = _finished_from_result(block)
        if finished.id in finished_ids:
            return None
        return finished
    return None


def _record_web_tool(
    event: ToolFinished, finished_ids: set[str], tools_used: list[dict[str, Any]],
) -> ToolFinished:
    finished_ids.add(event.id)
    tools_used.append({
        "id": event.id, "name": event.name, "ok": event.ok,
        "summary": event.summary, "sources": event.sources,
    })
    return event


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
    - `web_search` y `web_fetch` corren en los servidores de Claude. Se declaran junto a las
      herramientas propias, pero no se ejecutan aquí ni se responden con `tool_result`.
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
        web_tools_enabled: bool = True,
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
        if web_tools_enabled:
            self._tools.extend(dict(tool) for tool in _SERVER_WEB_TOOLS)

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
                started_ids: set[str] = set()
                finished_ids: set[str] = set()
                try:
                    async with self._client.beta.messages.stream(**self._request_params(conversation)) as stream:
                        async for event in stream:
                            server_event = _server_event_from_stream(event)
                            if isinstance(server_event, ToolStarted) and server_event.id not in started_ids:
                                started_ids.add(server_event.id)
                                yield server_event
                            elif (
                                isinstance(server_event, ToolFinished)
                                and server_event.id in started_ids
                                and server_event.id not in finished_ids
                            ):
                                yield _record_web_tool(server_event, finished_ids, tools_used)
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
                # Si el stream no traía el `input` al arrancar el bloque, sale del mensaje final.
                for block in content:
                    pending = _deferred_server_event(block, started_ids, finished_ids)
                    if isinstance(pending, ToolStarted):
                        started_ids.add(pending.id)
                        yield pending
                    elif isinstance(pending, ToolFinished):
                        yield _record_web_tool(pending, finished_ids, tools_used)
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
