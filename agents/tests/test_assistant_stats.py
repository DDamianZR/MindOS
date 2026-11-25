"""
Fase 8: `GET /assistant/stats` resume el uso real del asistente desde que arrancó el servicio.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from agents.src import main as agents_main
from agents.src.api import assistant_router
from agents.src.application.assistant.toolbox import AssistantToolbox
from agents.src.application.ports.personal_agent import ToolFinished, TurnFailed
from agents.src.config import settings
from agents.src.infrastructure.adapters.demo_personal_agent import DemoPersonalAgent
from agents.src.infrastructure.adapters.in_memory_conversation_store import (
    InMemoryConversationStore,
)
from agents.src.infrastructure.adapters.in_memory_usage_recorder import InMemoryUsageRecorder
from agents.tests.test_assistant_toolbox import FakeMemoryGateway


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for chunk in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in chunk.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture
def client(monkeypatch):
    recorder = InMemoryUsageRecorder()
    monkeypatch.setattr(agents_main, "conversation_store", InMemoryConversationStore())
    monkeypatch.setattr(assistant_router, "_busy_conversations", set())
    agents_main.app.dependency_overrides[agents_main.get_personal_agent] = (
        lambda: DemoPersonalAgent(AssistantToolbox(FakeMemoryGateway()), chunk_delay=0)
    )
    agents_main.app.dependency_overrides[agents_main.get_usage_recorder] = lambda: recorder
    yield TestClient(agents_main.app)
    agents_main.app.dependency_overrides.clear()


def test_two_turns_in_the_same_conversation_show_up_in_stats(client):
    first = client.post("/api/v1/agents/assistant/chat", json={"message": "¿Qué base de datos elegí?"})
    assert first.status_code == 200
    events = _parse_sse(first.text)
    conversation_id = events[0][1]["conversation_id"]
    assert events[-1][0] == "done"

    second = client.post(
        "/api/v1/agents/assistant/chat",
        json={"message": "¿Y Traefik?", "conversation_id": conversation_id},
    )
    assert second.status_code == 200

    body = client.get("/api/v1/agents/assistant/stats").json()
    today = datetime.now(timezone.utc).date().isoformat()

    assert body["provider"] == "demo" and body["model"] == "demo"
    assert body["conversations"] == 1
    assert body["turns"] == 2
    assert body["failed_turns"] == 0
    assert body["tool_calls"] == [{"key": "search_memory", "count": 2}]
    assert body["usage"] == {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    assert body["cache_hit_ratio"] is None
    assert body["estimated_cost_usd"] == 0
    assert body["avg_turn_seconds"] >= 0
    dates = [day["date"] for day in body["turns_by_day"]]
    assert len(body["turns_by_day"]) == 14
    assert dates == sorted(dates)
    assert body["turns_by_day"][-1] == {"date": today, "turns": 2}
    assert all(day["turns"] == 0 for day in body["turns_by_day"][:-1])
    datetime.fromisoformat(body["since"])


def test_a_failed_turn_is_counted_without_tokens(client):
    class FailingAgent(DemoPersonalAgent):
        async def stream_reply(self, conversation, user_text):
            yield ToolFinished(id="t1", name="save_memory", ok=False, summary="no se guardó", sources=[])
            yield TurnFailed("No pude completar la respuesta.")

    agents_main.app.dependency_overrides[agents_main.get_personal_agent] = (
        lambda: FailingAgent(AssistantToolbox(FakeMemoryGateway()))
    )
    events = _parse_sse(client.post("/api/v1/agents/assistant/chat", json={"message": "Guarda esto"}).text)

    assert [kind for kind, _ in events] == ["conversation", "tool_end", "error"]
    body = client.get("/api/v1/agents/assistant/stats").json()
    assert body["turns"] == 1
    assert body["failed_turns"] == 1
    assert body["conversations"] == 1
    assert body["tool_calls"] == [{"key": "save_memory", "count": 1}]
    assert body["usage"]["input_tokens"] == 0
    assert body["estimated_cost_usd"] == 0
    assert assistant_router._busy_conversations == set()


def test_an_unexpected_stream_error_is_a_failed_turn(client):
    class ExplodingAgent(DemoPersonalAgent):
        async def stream_reply(self, conversation, user_text):
            raise RuntimeError("se rompió algo")
            yield  # pragma: no cover

    agents_main.app.dependency_overrides[agents_main.get_personal_agent] = (
        lambda: ExplodingAgent(AssistantToolbox(FakeMemoryGateway()))
    )
    events = _parse_sse(client.post("/api/v1/agents/assistant/chat", json={"message": "Hola"}).text)

    assert [kind for kind, _ in events] == ["conversation", "error"]
    body = client.get("/api/v1/agents/assistant/stats").json()
    assert body["turns"] == 1
    assert body["failed_turns"] == 1
    assert body["tool_calls"] == []
    assert assistant_router._busy_conversations == set()


def test_a_rejected_message_is_not_a_turn(client):
    resp = client.post(
        "/api/v1/agents/assistant/chat",
        json={"message": "Hola", "conversation_id": "no-existe"},
    )
    assert resp.status_code == 404
    assert client.get("/api/v1/agents/assistant/stats").json()["turns"] == 0


def test_provider_follows_the_injected_agent(client):
    class SonnetAgent(DemoPersonalAgent):
        model_name = "claude-sonnet-5-5"

    agents_main.app.dependency_overrides[agents_main.get_personal_agent] = (
        lambda: SonnetAgent(AssistantToolbox(FakeMemoryGateway()), chunk_delay=0)
    )
    body = client.get("/api/v1/agents/assistant/stats").json()
    assert body["provider"] == "anthropic"
    assert body["model"] == "claude-sonnet-5-5"
    assert body["estimated_cost_usd"] == 0
    assert len(body["turns_by_day"]) == 14


async def test_recorder_prices_a_real_sonnet_usage_by_hand():
    """Dos turnos con el uso que deja un turno real de Sonnet, sumados."""
    recorder = InMemoryUsageRecorder()
    await recorder.record_turn(
        "conv-1",
        ok=True,
        duration_seconds=1.5,
        tools=["search_memory"],
        usage={
            "input_tokens": 2100,
            "output_tokens": 55,
            "cache_read_input_tokens": 850,
            "cache_creation_input_tokens": 0,
        },
    )
    await recorder.record_turn(
        "conv-1",
        ok=True,
        duration_seconds=2.5,
        tools=["search_memory", "save_memory"],
        usage={
            "input_tokens": 400,
            "output_tokens": 80,
            "cache_read_input_tokens": 2100,
            "cache_creation_input_tokens": 1500,
        },
    )

    snap = (await recorder.snapshot("claude-sonnet-5-5"))

    assert snap.conversations == 1
    assert snap.turns == 2
    assert snap.failed_turns == 0
    assert [(item.key, item.count) for item in snap.tool_calls] == [
        ("search_memory", 2),
        ("save_memory", 1),
    ]
    assert snap.usage.input_tokens == 2500
    assert snap.usage.output_tokens == 135
    assert snap.usage.cache_read_input_tokens == 2950
    assert snap.usage.cache_creation_input_tokens == 1500
    assert snap.cache_hit_ratio == pytest.approx(2950 / (2500 + 2950 + 1500))
    assert snap.avg_turn_seconds == 2.0

    # Tarifa de claude-sonnet-5-5, USD por millón: input 2, output 10, cache_read 0.10, cache_write 2.50.
    # (2500*2 + 135*10 + 2950*0.10 + 1500*2.50) / 1_000_000 = 0.010395
    hand = round((2500 * 2 + 135 * 10 + 2950 * 0.10 + 1500 * 2.50) / 1_000_000, 6)
    assert hand == 0.010395
    rates = settings.ASSISTANT_PRICING["claude-sonnet-5-5"]
    from_settings = round(
        (
            2500 * rates["input"]
            + 135 * rates["output"]
            + 2950 * rates["cache_read"]
            + 1500 * rates["cache_write"]
        ) / 1_000_000,
        6,
    )
    assert snap.estimated_cost_usd == hand == from_settings
    assert (await recorder.snapshot("demo")).estimated_cost_usd == 0.0
    assert (await recorder.snapshot("modelo-sin-tarifa")).estimated_cost_usd == 0.0


async def test_turns_by_day_is_fourteen_utc_days_ending_today_with_zeros():
    today = datetime(2026, 11, 24, 15, tzinfo=timezone.utc)
    recorder = InMemoryUsageRecorder(clock=lambda: today)
    await recorder.record_turn("old", ok=True, duration_seconds=1, tools=[], at=today - timedelta(days=14))
    await recorder.record_turn("edge", ok=True, duration_seconds=1, tools=[], at=today - timedelta(days=13))
    await recorder.record_turn("mid", ok=True, duration_seconds=1, tools=[], at=datetime(2026, 11, 20, tzinfo=timezone.utc))
    await recorder.record_turn("now", ok=True, duration_seconds=1, tools=[], at=today)
    await recorder.record_turn("now", ok=False, duration_seconds=1, tools=[], at=today)

    snap = (await recorder.snapshot("demo"))
    days = snap.turns_by_day

    assert snap.since == "2026-11-24T15:00:00+00:00"
    assert snap.turns == 5
    assert snap.failed_turns == 1
    assert snap.conversations == 4
    assert len(days) == 14
    assert [day.date for day in days] == [
        (today.date() - timedelta(days=offset)).isoformat() for offset in range(13, -1, -1)
    ]
    by_date = {day.date: day.turns for day in days}
    assert "2026-11-10" not in by_date
    assert by_date["2026-11-11"] == 1
    assert by_date["2026-11-12"] == 0
    assert by_date["2026-11-20"] == 1
    assert by_date["2026-11-24"] == 2
    assert sum(day.turns for day in days) == 4
    assert snap.cache_hit_ratio is None
    assert snap.estimated_cost_usd == 0.0


async def test_recorder_keeps_only_the_last_5000_turns():
    recorder = InMemoryUsageRecorder()
    for index in range(5001):
        await recorder.record_turn(
            "dropped" if index == 0 else "kept",
            ok=True,
            duration_seconds=0,
            tools=["search_memory"] if index == 0 else [],
            usage={"input_tokens": 1000 if index == 0 else 1},
        )

    snap = (await recorder.snapshot("demo"))
    assert snap.turns == 5000
    assert snap.conversations == 1
    assert snap.usage.input_tokens == 5000
    assert snap.tool_calls == []
    assert snap.estimated_cost_usd == 0.0
