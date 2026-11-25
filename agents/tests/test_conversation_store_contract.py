"""Contrato de ConversationStore: la memoria y Postgres se comportan igual."""

import os
from uuid import UUID

import pytest
from sqlalchemy import text

from agents.src.infrastructure.adapters.in_memory_conversation_store import (
    InMemoryConversationStore,
)
from agents.src.infrastructure.adapters.pg_conversation_store import PgConversationStore
from agents.src.infrastructure.database.session import create_session_factory

_HISTORY = [
    {"role": "user", "content": "¿Qué base de datos elegí?"},
    {
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "Reviso la memoria.", "signature": "sig-primera"},
            {"type": "text", "text": "Déjame revisar."},
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "search_memory",
                "input": {"query": "base de datos", "limit": 5},
            },
        ],
    },
    {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": "Postgres", "is_error": False},
        ],
    },
]
_TRANSCRIPT = [
    {"role": "user", "text": "¿Qué base de datos elegí?"},
    {
        "role": "assistant",
        "text": "Déjame revisar.",
        "stop_reason": "end_turn",
        "tools": [{
            "id": "toolu_1",
            "name": "search_memory",
            "ok": True,
            "summary": "1 fragmento encontrado",
            "sources": [{
                "kind": "memory",
                "title": "Decisión: usar Postgres",
                "url": None,
                "node_id": "0193-a",
                "object_type": "decision",
                "score": 0.91,
            }],
        }],
    },
]
_HISTORY_UPDATED = [
    *_HISTORY,
    {"role": "assistant", "content": [{"type": "text", "text": "Elegiste Postgres.", "signature": "sig-segunda"}]},
]
_TRANSCRIPT_UPDATED = [
    *_TRANSCRIPT,
    {"role": "assistant", "text": "Elegiste Postgres.", "stop_reason": "end_turn", "tools": []},
]


@pytest.fixture(params=[
    "memory",
    pytest.param("postgres", marks=pytest.mark.integration),
])
async def store(request):
    if request.param == "memory":
        yield InMemoryConversationStore()
        return

    url = os.environ.get("MINDOS_TEST_AGENTS_DATABASE_URL")
    if not url:
        pytest.skip("MINDOS_TEST_AGENTS_DATABASE_URL no está definida")
    engine, session_factory = create_session_factory(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE agent_conversations CASCADE"))
        yield PgConversationStore(session_factory)
    finally:
        await engine.dispose()


async def test_conversation_store_contract(store):
    assert await store.get("no-existe") is None

    created = await store.create()
    assert UUID(created.id).version == 7
    loaded = await store.get(created.id)
    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.started_at == created.started_at
    assert "hora local del servidor" in loaded.started_at
    assert loaded.messages == []
    assert loaded.transcript == []

    created.messages = _HISTORY
    created.transcript = _TRANSCRIPT
    await store.save(created)
    loaded = await store.get(created.id)
    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.started_at == created.started_at
    assert loaded.messages == _HISTORY
    assert loaded.transcript == _TRANSCRIPT

    created.messages = _HISTORY_UPDATED
    created.transcript = _TRANSCRIPT_UPDATED
    await store.save(created)
    loaded = await store.get(created.id)
    assert loaded is not None
    assert loaded.messages == _HISTORY_UPDATED
    assert loaded.transcript == _TRANSCRIPT_UPDATED
    assert loaded.started_at == created.started_at
