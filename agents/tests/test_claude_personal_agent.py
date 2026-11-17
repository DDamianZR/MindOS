"""
F7-T3: el asistente personal sobre Claude ejecuta el bucle de herramientas con streaming,
mantiene el historial solo-anexar y consistente (nunca queda un turno a medias) y arma la
petición con la forma que exige Claude Sonnet 5.5.

Dos niveles de doble de prueba:
- `FakeClient`: guiona respuestas ya parseadas; cubre la lógica del bucle.
- SDK real + transporte simulado: cubre que la petición serializa y que el stream SSE del
  protocolo se interpreta bien. Es lo más cerca de la API real que se llega sin credencial.
"""
import json
from types import SimpleNamespace

import anthropic
import httpx2

from agents.src.application.assistant.toolbox import AssistantToolbox
from agents.src.application.ports.personal_agent import Conversation
from agents.src.infrastructure.adapters.claude_personal_agent import (
    ClaudePersonalAgent,
    _echoable_content,
)
from agents.tests.test_assistant_toolbox import FakeMemoryGateway

# --- Doble de prueba de alto nivel ---

def _block(type_, **fields):
    return SimpleNamespace(type=type_, **fields)


def _message(content, stop_reason="end_turn", model="claude-sonnet-5-5", **usage):
    return SimpleNamespace(
        content=content, stop_reason=stop_reason, model=model, stop_details=None,
        usage=SimpleNamespace(
            input_tokens=usage.get("input_tokens", 100), output_tokens=usage.get("output_tokens", 20),
            cache_read_input_tokens=usage.get("cache_read", 0), cache_creation_input_tokens=0,
        ),
    )


def _delta(kind, **fields):
    return SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type=kind, **fields))


class _FakeStream:
    def __init__(self, events, message):
        self._events, self._message = events, message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def __aiter__(self):
        for event in self._events:
            if isinstance(event, Exception):
                raise event
            yield event

    async def get_final_message(self):
        return self._message


class FakeClient:
    """Cada llamada a `beta.messages.stream` consume la siguiente respuesta guionizada."""
    def __init__(self, script):
        self._script = list(script)
        self.requests: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **params):
        # Copia superficial de `messages`: la lista real sigue creciendo después de la llamada.
        self.requests.append({**params, "messages": list(params["messages"])})
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakeStream(*item)


def _agent(script, gateway=None, **kwargs):
    client = FakeClient(script)
    agent = ClaudePersonalAgent(client, AssistantToolbox(gateway or FakeMemoryGateway()), **kwargs)
    return agent, client


def _conversation():
    return Conversation(id="conv-1", started_at="lunes 16 de noviembre de 2026, 10:00")


async def _run(agent, conversation, text):
    return [event async for event in agent.stream_reply(conversation, text)]


def _api_error(cls, status):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx2.Response(status, request=request), body=None)


SEARCH_ROUND = (
    [_delta("thinking_delta", thinking="Reviso la memoria."), _delta("text_delta", text="Déjame revisar. ")],
    _message(
        [
            _block("thinking", thinking="Reviso la memoria.", signature="sig-1"),
            _block("text", text="Déjame revisar. "),
            _block("tool_use", id="toolu_1", name="search_memory", input={"query": "base de datos"}),
        ],
        stop_reason="tool_use", input_tokens=900, output_tokens=40,
    ),
)
ANSWER_ROUND = (
    [_delta("text_delta", text="Elegiste "), _delta("text_delta", text="Postgres.")],
    _message([_block("text", text="Elegiste Postgres.")], input_tokens=1200, output_tokens=15, cache_read=850),
)


async def test_a_turn_with_one_tool_round_streams_events_in_order_and_keeps_history_consistent():
    agent, client = _agent([SEARCH_ROUND, ANSWER_ROUND])
    conversation = _conversation()

    events = await _run(agent, conversation, "¿Qué base de datos elegí?")

    assert [e.type for e in events] == ["thinking", "text", "tool_start", "tool_end", "text", "text", "done"]
    tool_start, tool_end, done = events[2], events[3], events[-1]
    assert (tool_start.label, tool_start.input) == ("Buscando en tu memoria", {"query": "base de datos"})
    assert tool_end.ok and tool_end.summary == "2 fragmentos encontrados"
    assert [s["title"] for s in tool_end.sources] == ["Decisión: usar Postgres", "Nota de Traefik"]
    assert done.stop_reason == "end_turn"
    assert done.usage == {
        "input_tokens": 2100, "output_tokens": 55, "cache_read_input_tokens": 850, "cache_creation_input_tokens": 0,
    }

    # Historial: usuario -> asistente (con su razonamiento intacto) -> resultados -> asistente.
    assert [m["role"] for m in conversation.messages] == ["user", "assistant", "user", "assistant"]
    assert conversation.messages[1]["content"] is not None
    assert [b.type for b in conversation.messages[1]["content"]] == ["thinking", "text", "tool_use"]
    results = conversation.messages[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["toolu_1"]
    assert results[0]["is_error"] is False

    # La segunda petición reenvía exactamente lo acumulado hasta ese punto.
    assert len(client.requests) == 2
    assert [m["role"] for m in client.requests[1]["messages"]] == ["user", "assistant", "user"]

    assert conversation.transcript == [
        {"role": "user", "text": "¿Qué base de datos elegí?"},
        {
            "role": "assistant", "text": "Déjame revisar. Elegiste Postgres.", "stop_reason": "end_turn",
            "tools": [{
                "id": "toolu_1", "name": "search_memory", "ok": True,
                "summary": "2 fragmentos encontrados", "sources": tool_end.sources,
            }],
        },
    ]


async def test_request_has_the_shape_claude_sonnet_5_5_requires():
    agent, client = _agent([ANSWER_ROUND], owner_name="Damián")
    await _run(agent, _conversation(), "Hola")

    request = client.requests[0]
    assert request["model"] == "claude-sonnet-5-5"
    # Razonamiento adaptativo (los presupuestos manuales y `disabled` devuelven 400 en este modelo).
    assert request["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert request["output_config"] == {"effort": "low"}
    # Forzar una herramienta devuelve 400: `tool_choice` no se envía (queda en `auto`).
    assert "tool_choice" not in request
    assert "temperature" not in request and "top_p" not in request
    assert request["betas"] == ["server-side-fallback-2026-07-01"] and request["fallbacks"] == "default"
    assert all(tool["eager_input_streaming"] is True for tool in request["tools"])

    base, context = request["system"]
    assert base["cache_control"] == {"type": "ephemeral"}
    assert "2026" not in base["text"], "el bloque cacheado no puede contener nada que cambie"
    assert "lunes 16 de noviembre de 2026" in context["text"] and "Damián" in context["text"]


async def test_system_prompt_and_tools_stay_identical_across_turns():
    """El proveedor rechaza reenviar razonamiento si `system` o `tools` cambiaron desde que se produjo."""
    agent, client = _agent([SEARCH_ROUND, ANSWER_ROUND, ANSWER_ROUND])
    conversation = _conversation()
    await _run(agent, conversation, "Primera")
    await _run(agent, conversation, "Segunda")

    first, _, third = client.requests
    assert first["system"] == third["system"]
    assert first["tools"] == third["tools"]
    # Y el historial previo llega intacto como prefijo del nuevo.
    assert third["messages"][:4] == conversation.messages[:4]


async def test_parallel_tool_calls_are_answered_in_a_single_user_message():
    two_tools = (
        [],
        _message(
            [
                _block("tool_use", id="toolu_a", name="search_memory", input={"query": "postgres"}),
                _block("tool_use", id="toolu_b", name="list_decisions", input={"topic": "postgres"}),
            ],
            stop_reason="tool_use",
        ),
    )
    agent, _ = _agent([two_tools, ANSWER_ROUND])
    conversation = _conversation()

    events = await _run(agent, conversation, "Resume lo de postgres")

    assert [e.type for e in events[:4]] == ["tool_start", "tool_start", "tool_end", "tool_end"]
    assert [r["tool_use_id"] for r in conversation.messages[2]["content"]] == ["toolu_a", "toolu_b"]


async def test_invalid_tool_input_goes_back_to_the_model_as_an_error_result():
    bad_call = (
        [],
        _message([_block("tool_use", id="toolu_x", name="search_memory", input={"limit": 3})], stop_reason="tool_use"),
    )
    agent, _ = _agent([bad_call, ANSWER_ROUND])
    conversation = _conversation()

    events = await _run(agent, conversation, "Busca algo")

    assert events[1].type == "tool_end" and events[1].ok is False
    result = conversation.messages[2]["content"][0]
    assert result["is_error"] is True and "INVALID_INPUT" in result["content"]
    assert events[-1].type == "done", "el modelo recibe el error y puede corregir; el turno no se rompe"


async def test_api_error_ends_the_turn_with_a_readable_message_and_rolls_history_back():
    agent, _ = _agent([_api_error(anthropic.AuthenticationError, 401)])
    conversation = _conversation()

    events = await _run(agent, conversation, "Hola")

    assert [e.type for e in events] == ["error"]
    assert "ANTHROPIC_API_KEY" in events[0].message
    assert conversation.messages == [] and conversation.transcript == []


async def test_error_after_a_tool_round_rolls_back_the_whole_turn():
    agent, _ = _agent([SEARCH_ROUND, _api_error(anthropic.RateLimitError, 429)])
    conversation = _conversation()

    events = await _run(agent, conversation, "¿Qué base de datos elegí?")

    assert events[-1].type == "error" and "limitando" in events[-1].message
    assert conversation.messages == [], "ni el mensaje del usuario ni la ronda de herramientas quedan a medias"


async def test_refusal_is_reported_and_not_kept_in_history():
    refused = ([], _message([], stop_reason="refusal"))
    agent, _ = _agent([refused])
    conversation = _conversation()

    events = await _run(agent, conversation, "…")

    assert [e.type for e in events] == ["error"]
    assert "declinó" in events[0].message
    assert conversation.messages == []


async def test_client_disconnect_mid_turn_leaves_history_untouched():
    agent, _ = _agent([SEARCH_ROUND, ANSWER_ROUND])
    conversation = _conversation()

    stream = agent.stream_reply(conversation, "¿Qué base de datos elegí?")
    assert (await anext(stream)).type == "thinking"
    await stream.aclose()  # lo que hace el servidor cuando el navegador cierra la conexión

    assert conversation.messages == [] and conversation.transcript == []


async def test_tool_loop_that_never_converges_is_cut_off():
    agent, client = _agent([SEARCH_ROUND] * 3, max_tool_rounds=2)
    conversation = _conversation()

    events = await _run(agent, conversation, "Sigue buscando")

    assert events[-1].type == "error" and "demasiadas consultas" in events[-1].message
    assert len(client.requests) == 3
    assert conversation.messages == []


async def test_truncated_tool_call_is_never_executed():
    gateway = FakeMemoryGateway()
    truncated = (
        [],
        _message(
            [_block("tool_use", id="toolu_t", name="save_memory", input={"title": "A medias", "content": "Se cor"})],
            stop_reason="max_tokens",
        ),
    )
    agent, _ = _agent([truncated], gateway=gateway)

    events = await _run(agent, _conversation(), "Guarda esto")

    assert events[-1].type == "error" and "límite de tokens" in events[-1].message
    assert gateway.ingested == [], "una entrada truncada parsea como objeto válido: no debe guardarse"


async def test_unparseable_tool_json_restarts_the_turn_and_tells_the_client_to_discard_partial_text():
    broken = ([_delta("text_delta", text="Voy a "), ValueError("bad json")], _message([]))
    agent, client = _agent([broken, ANSWER_ROUND])
    conversation = _conversation()

    events = await _run(agent, conversation, "Hola")

    assert [e.type for e in events] == ["text", "restart", "text", "text", "done"]
    assert conversation.transcript[-1]["text"] == "Elegiste Postgres."
    assert len(client.requests) == 2


def test_blocks_before_a_mid_output_fallback_are_not_echoed_back():
    """Tras un relevo de modelo a mitad de respuesta, el razonamiento y las llamadas del modelo
    que declinó no se reenvían; el bloque `fallback` se queda exactamente donde apareció."""
    content = [
        _block("thinking", thinking="…", signature="s"), _block("text", text="Parcial"),
        _block("tool_use", id="toolu_old", name="search_memory", input={}),
        _block("fallback"),
        _block("thinking", thinking="…", signature="s2"), _block("text", text="Sigo yo."),
        _block("tool_use", id="toolu_new", name="search_memory", input={"query": "x"}),
    ]

    kept = _echoable_content(content)

    assert [b.type for b in kept] == ["text", "fallback", "thinking", "text", "tool_use"]
    assert kept[-1].id == "toolu_new"
    assert _echoable_content(content[4:]) == content[4:], "sin relevo, todo se reenvía intacto"


# --- SDK real con transporte simulado ---

def _sse(events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def _wire_message_start():
    return {"type": "message_start", "message": {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
        "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 500, "output_tokens": 1},
    }}


def _wire_stop(stop_reason, output_tokens):
    return [
        {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
         "usage": {"output_tokens": output_tokens}},
        {"type": "message_stop"},
    ]


WIRE_TOOL_ROUND = _sse([
    _wire_message_start(),
    {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "Busco en la memoria."}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "sig-abc"}},
    {"type": "content_block_stop", "index": 0},
    {"type": "content_block_start", "index": 1,
     "content_block": {"type": "tool_use", "id": "toolu_wire", "name": "search_memory", "input": {}}},
    {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '{"query": "base'}},
    {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": ' de datos"}'}},
    {"type": "content_block_stop", "index": 1},
    *_wire_stop("tool_use", 30),
])
WIRE_ANSWER_ROUND = _sse([
    _wire_message_start(),
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Elegiste Postgres."}},
    {"type": "content_block_stop", "index": 0},
    *_wire_stop("end_turn", 8),
])


async def test_real_sdk_serializes_the_request_and_parses_the_stream():
    bodies, headers = [], []
    responses = [WIRE_TOOL_ROUND, WIRE_ANSWER_ROUND]

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        headers.append(request.headers)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=responses.pop(0))

    client = anthropic.AsyncAnthropic(
        api_key="sk-ant-test", max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    agent = ClaudePersonalAgent(client, AssistantToolbox(FakeMemoryGateway()))
    conversation = _conversation()

    events = await _run(agent, conversation, "¿Qué base de datos elegí?")

    assert [e.type for e in events] == ["thinking", "tool_start", "tool_end", "text", "done"]
    assert events[1].input == {"query": "base de datos"}, "los fragmentos de JSON se reensamblan"
    assert events[-1].usage["output_tokens"] == 38

    first, second = bodies
    assert "server-side-fallback-2026-07-01" in headers[0]["anthropic-beta"]
    assert first["stream"] is True and first["fallbacks"] == "default"
    assert first["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert first["output_config"] == {"effort": "low"} and first["cache_control"] == {"type": "ephemeral"}
    assert first["tools"][0]["name"] == "search_memory" and first["tools"][0]["eager_input_streaming"] is True
    assert first["messages"] == [{"role": "user", "content": "¿Qué base de datos elegí?"}]

    # El turno del asistente vuelve con su bloque de razonamiento y la firma sin tocar.
    assistant_turn, tool_results = second["messages"][1], second["messages"][2]
    assert assistant_turn["content"][0] == {"type": "thinking", "thinking": "Busco en la memoria.", "signature": "sig-abc"}
    assert assistant_turn["content"][1]["type"] == "tool_use" and assistant_turn["content"][1]["id"] == "toolu_wire"
    assert tool_results["content"][0]["type"] == "tool_result"
    assert tool_results["content"][0]["tool_use_id"] == "toolu_wire"
    assert second["system"] == first["system"] and second["tools"] == first["tools"]
