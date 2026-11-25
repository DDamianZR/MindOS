"""
Contrato de `UsageRecorderPort`: memoria y Postgres devuelven los mismos agregados.

La variante de Postgres lleva la marca `integration` y no corre sin
`MINDOS_TEST_AGENTS_DATABASE_URL`.
"""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from agents.src.application.ports.usage_recorder import UsageTotals
from agents.src.config import settings
from agents.src.infrastructure.adapters.in_memory_usage_recorder import InMemoryUsageRecorder
from agents.src.infrastructure.adapters.pg_usage_recorder import PgUsageRecorder
from agents.src.infrastructure.database.session import create_session_factory


def _database_url() -> str:
    url = os.environ.get("MINDOS_TEST_AGENTS_DATABASE_URL")
    if not url:
        pytest.skip("MINDOS_TEST_AGENTS_DATABASE_URL no está definida")
    return url


@asynccontextmanager
async def _usage_database():
    engine, sessions = create_session_factory(_database_url())
    try:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE agent_usage_turns CASCADE"))
        yield sessions
    finally:
        await engine.dispose()


@pytest.fixture(params=[
    "memory",
    pytest.param("postgres", marks=pytest.mark.integration),
])
async def make_usage_recorder(request):
    """Construye cada implementación. `clock` fijo para que «hoy» no dependa del reloj real."""
    if request.param == "memory":
        async def make_memory(clock=None):
            return InMemoryUsageRecorder(clock=clock)

        yield make_memory
        return

    async with _usage_database() as sessions:
        async def make_pg(clock=None):
            return PgUsageRecorder(sessions, clock=clock)

        yield make_pg


async def _record_two_sonnet_turns(
    recorder,
    *,
    first_at: datetime | None = None,
    second_at: datetime | None = None,
) -> None:
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
        at=first_at,
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
        at=second_at,
    )


async def test_recorder_prices_a_real_sonnet_usage_by_hand(make_usage_recorder):
    """Dos turnos con el uso que deja un turno real de Sonnet, sumados."""
    today = datetime(2026, 11, 24, 15, tzinfo=timezone.utc)
    recorder = await make_usage_recorder(clock=lambda: today)
    await _record_two_sonnet_turns(recorder)

    snap = await recorder.snapshot("claude-sonnet-5-5")

    assert snap.since == "2026-11-24T15:00:00+00:00"
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


async def test_turns_by_day_is_fourteen_utc_days_ending_today_with_zeros(make_usage_recorder):
    today = datetime(2026, 11, 24, 15, tzinfo=timezone.utc)
    recorder = await make_usage_recorder(clock=lambda: today)
    await recorder.record_turn("old", ok=True, duration_seconds=1, tools=[], at=today - timedelta(days=14))
    await recorder.record_turn("edge", ok=True, duration_seconds=1, tools=[], at=today - timedelta(days=13))
    await recorder.record_turn(
        "mid", ok=True, duration_seconds=1, tools=[], at=datetime(2026, 11, 20, tzinfo=timezone.utc)
    )
    await recorder.record_turn("now", ok=True, duration_seconds=1, tools=[], at=today)
    await recorder.record_turn("now", ok=False, duration_seconds=1, tools=[], at=today)

    snap = await recorder.snapshot("demo")
    days = snap.turns_by_day

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
    # Memoria ancla `since` al crear el recorder; Postgres, al `at` del primer turno.
    # Con turnos anteriores a ese reloj el valor no es el mismo, y cada uno lo afirma aparte.
    datetime.fromisoformat(snap.since)


async def test_without_turns_cache_ratio_is_null_and_cost_is_zero(make_usage_recorder):
    today = datetime(2026, 11, 24, 15, tzinfo=timezone.utc)
    recorder = await make_usage_recorder(clock=lambda: today)

    snap = await recorder.snapshot("claude-sonnet-5-5")

    assert snap.since == "2026-11-24T15:00:00+00:00"
    assert snap.conversations == 0
    assert snap.turns == 0
    assert snap.failed_turns == 0
    assert snap.tool_calls == []
    assert snap.usage == UsageTotals()
    assert snap.cache_hit_ratio is None
    assert snap.estimated_cost_usd == 0.0
    assert snap.avg_turn_seconds is None
    assert [day.date for day in snap.turns_by_day] == [
        (today.date() - timedelta(days=offset)).isoformat() for offset in range(13, -1, -1)
    ]
    assert all(day.turns == 0 for day in snap.turns_by_day)


async def test_a_failed_turn_counts_in_failed_turns(make_usage_recorder):
    recorder = await make_usage_recorder()
    await recorder.record_turn(
        "conv-1",
        ok=False,
        duration_seconds=1,
        tools=["zeta", "mu", "alpha", "mu"],
    )

    snap = await recorder.snapshot("claude-sonnet-5-5")

    assert snap.turns == 1
    assert snap.failed_turns == 1
    assert snap.conversations == 1
    assert [(item.key, item.count) for item in snap.tool_calls] == [
        ("mu", 2),
        ("alpha", 1),
        ("zeta", 1),
    ]
    assert snap.usage == UsageTotals()
    assert snap.cache_hit_ratio is None
    assert snap.estimated_cost_usd == 0.0


@pytest.mark.integration
async def test_turns_remain_when_a_new_recorder_opens_the_same_database():
    morning = datetime(2026, 11, 24, 15, tzinfo=timezone.utc)
    evening = datetime(2026, 11, 24, 18, tzinfo=timezone.utc)
    first_at = datetime(2026, 11, 10, 15, 30, tzinfo=timezone.utc)
    async with _usage_database() as sessions:
        first = PgUsageRecorder(sessions, clock=lambda: morning)
        await _record_two_sonnet_turns(first, first_at=first_at, second_at=morning)
        snap = await first.snapshot("claude-sonnet-5-5")

        restarted = PgUsageRecorder(sessions, clock=lambda: evening)
        again = await restarted.snapshot("claude-sonnet-5-5")

    assert snap.since == first_at.isoformat()
    assert snap.since != morning.isoformat()
    assert again == snap
    assert again.since != evening.isoformat()
