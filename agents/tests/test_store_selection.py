"""Elegir el almacén del servicio de agentes sin abrir Postgres."""
import pytest

from agents.src.infrastructure.adapters.in_memory_conversation_store import (
    InMemoryConversationStore,
)
from agents.src.infrastructure.adapters.in_memory_routine_store import InMemoryRoutineStore
from agents.src.infrastructure.adapters.in_memory_usage_recorder import InMemoryUsageRecorder
from agents.src.main import build_stores

_UNUSED_URL = "postgresql+asyncpg://no-se-usa/mindos"


def test_in_memory_builds_the_three_stores_without_an_engine():
    stores = build_stores("in_memory", _UNUSED_URL)

    assert isinstance(stores.conversations, InMemoryConversationStore)
    assert isinstance(stores.routines, InMemoryRoutineStore)
    assert isinstance(stores.usage, InMemoryUsageRecorder)
    assert stores.engine is None


def test_an_unknown_store_is_rejected_in_spanish():
    with pytest.raises(ValueError) as caught:
        build_stores("archivo", _UNUSED_URL)

    message = str(caught.value)
    assert "in_memory" in message
    assert "postgres" in message
    assert "almacén" in message
