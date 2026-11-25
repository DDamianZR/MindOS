"""Ida y vuelta de una conversación por Postgres: el historial restaurado se reenvía igual."""

import json
import os

import anthropic
import httpx2
import pytest
from sqlalchemy import text

from agents.src.application.assistant.toolbox import AssistantToolbox
from agents.src.infrastructure.adapters.claude_personal_agent import ClaudePersonalAgent
from agents.src.infrastructure.adapters.pg_conversation_store import PgConversationStore
from agents.src.infrastructure.adapters.provider_serialization import to_jsonable
from agents.src.infrastructure.database.session import create_session_factory
from agents.tests.test_assistant_toolbox import FakeMemoryGateway

pytestmark = pytest.mark.integration


def _sse(events):
    return "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events).encode()


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


# Mismo guion que el transporte simulado del asistente: un turno con herramientas y su firma.
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


def _scripted_agent(script: list[bytes], *, fail_after: bool = False):
    bodies: list[dict] = []
    pending = list(script)

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        if pending:
            return httpx2.Response(
                200, headers={"content-type": "text/event-stream"}, content=pending.pop(0),
            )
        if fail_after:
            return httpx2.Response(
                429,
                headers={"content-type": "application/json"},
                content=b'{"type":"error","error":{"type":"rate_limit_error","message":"slow down"}}',
            )
        raise AssertionError("petición inesperada")

    client = anthropic.AsyncAnthropic(
        api_key="sk-ant-test",
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    agent = ClaudePersonalAgent(client, AssistantToolbox(FakeMemoryGateway()))
    return agent, bodies


async def _collect(agent, conversation, user_text):
    return [event async for event in agent.stream_reply(conversation, user_text)]


@pytest.fixture
async def session_factory():
    url = os.environ.get("MINDOS_TEST_AGENTS_DATABASE_URL")
    if not url:
        pytest.skip("MINDOS_TEST_AGENTS_DATABASE_URL no está definida")
    engine, factory = create_session_factory(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE agent_conversations CASCADE"))
        yield factory
    finally:
        await engine.dispose()


async def test_restored_history_produces_the_same_request_as_the_live_objects(session_factory):
    store = PgConversationStore(session_factory)
    conversation = await store.create()
    live_agent, live_bodies = _scripted_agent([WIRE_TOOL_ROUND, WIRE_ANSWER_ROUND, WIRE_ANSWER_ROUND])

    await _collect(live_agent, conversation, "¿Qué base de datos elegí?")
    await store.save(conversation)
    restored = await PgConversationStore(session_factory).get(conversation.id)
    assert restored is not None

    await _collect(live_agent, conversation, "Gracias")
    restored_agent, restored_bodies = _scripted_agent([WIRE_ANSWER_ROUND])
    await _collect(restored_agent, restored, "Gracias")

    live_second = live_bodies[2]
    restored_second = restored_bodies[0]
    assert restored_second["messages"] == live_second["messages"]
    assert restored_second["system"] == live_second["system"]
    assert restored_second["tools"] == live_second["tools"]


async def test_restored_thinking_block_keeps_the_signature_byte_for_byte(session_factory):
    store = PgConversationStore(session_factory)
    conversation = await store.create()
    agent, _bodies = _scripted_agent([WIRE_TOOL_ROUND, WIRE_ANSWER_ROUND])
    await _collect(agent, conversation, "¿Qué base de datos elegí?")

    signature = conversation.messages[1]["content"][0].signature
    assert signature == "sig-abc"
    await store.save(conversation)

    restored = await PgConversationStore(session_factory).get(conversation.id)
    assert restored is not None
    block = restored.messages[1]["content"][0]
    assert block["type"] == "thinking"
    assert block["signature"] == signature
    assert block["thinking"] == conversation.messages[1]["content"][0].thinking


async def test_failed_turn_then_save_keeps_the_history_from_before_the_turn(session_factory):
    store = PgConversationStore(session_factory)
    conversation = await store.create()
    agent, _bodies = _scripted_agent(
        [WIRE_TOOL_ROUND, WIRE_ANSWER_ROUND, WIRE_TOOL_ROUND], fail_after=True,
    )
    await _collect(agent, conversation, "¿Qué base de datos elegí?")
    await store.save(conversation)
    expected_messages = to_jsonable(conversation.messages)
    expected_transcript = to_jsonable(conversation.transcript)
    assert expected_messages

    follow_up = "Sigue con otra pregunta distinta"
    events = await _collect(agent, conversation, follow_up)
    assert events[-1].type == "error"
    assert to_jsonable(conversation.messages) == expected_messages
    assert to_jsonable(conversation.transcript) == expected_transcript
    await store.save(conversation)

    restored = await PgConversationStore(session_factory).get(conversation.id)
    assert restored is not None
    assert restored.messages == expected_messages
    assert restored.transcript == expected_transcript
    stored = json.dumps(restored.messages, ensure_ascii=False)
    assert follow_up not in stored
