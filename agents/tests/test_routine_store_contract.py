"""
El mismo contrato de rutinas, contra el almacén en memoria y contra Postgres.

La variante de Postgres se salta si no hay `MINDOS_TEST_AGENTS_DATABASE_URL`,
y lleva la marca `integration` para que el CI (`-m "not integration"`) no la ejecute.
"""
import asyncio
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from agents.src.application.ports.routine_store import (
    RoutineAuthor,
    RoutineStatusName,
    RoutineStorePort,
)
from agents.src.infrastructure.adapters.in_memory_routine_store import InMemoryRoutineStore
from agents.src.infrastructure.adapters.pg_routine_store import PgRoutineStore
from agents.src.infrastructure.database.session import create_session_factory

_MEXICO = ZoneInfo("America/Mexico_City")
_DUE = datetime(2026, 11, 23, 9, 0, tzinfo=_MEXICO)
_CLEAN_TABLES = "TRUNCATE TABLE agent_routine_runs, agent_routines CASCADE"


def _database_url() -> str | None:
    url = os.environ.get("MINDOS_TEST_AGENTS_DATABASE_URL", "").strip()
    return url or None


async def _open_postgres() -> tuple[AsyncEngine, PgRoutineStore]:
    url = _database_url()
    if url is None:
        pytest.skip("No hay base de datos de prueba para las rutinas.")
    engine, sessions = create_session_factory(url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(_CLEAN_TABLES))
    except Exception:
        await engine.dispose()
        raise
    return engine, PgRoutineStore(sessions)


@pytest.fixture(params=[
    pytest.param("memory", id="memory"),
    pytest.param("postgres", id="postgres", marks=pytest.mark.integration),
])
async def routine_store(request):
    if request.param == "memory":
        yield InMemoryRoutineStore()
        return
    engine, store = await _open_postgres()
    try:
        yield store
    finally:
        await engine.dispose()


async def _create(
    store: RoutineStorePort,
    *,
    title: str = "Decisiones del lunes",
    status: RoutineStatusName = "active",
    created_by: RoutineAuthor | None = None,
    next_run_at: datetime | None = _DUE,
    prompt: str = "Resúmeme las decisiones pendientes",
):
    author: RoutineAuthor = created_by or (
        "assistant" if status == "pending_activation" else "user"
    )
    return await store.create(
        title=title,
        prompt=prompt,
        schedule="0 9 * * 1",
        schedule_description="cada lunes a las 09:00",
        timezone_name="America/Mexico_City",
        status=status,
        created_by=author,
        next_run_at=next_run_at,
    )


async def test_saved_routine_roundtrips_with_timezone(routine_store):
    nxt = datetime(2026, 11, 23, 9, 0, tzinfo=_MEXICO)
    created = await _create(routine_store, title="Lunes", next_run_at=nxt)

    assert len(created.id) == 36
    assert created.created_at.tzinfo is not None
    assert created.runs_count == 0
    assert created.last_run_at is None
    assert created.next_run_at is not None
    assert created.next_run_at.tzinfo is not None
    assert created.next_run_at == nxt
    assert created.status == "active"
    assert created.created_by == "user"
    assert created.timezone == "America/Mexico_City"
    assert created.schedule == "0 9 * * 1"
    assert created.schedule_description == "cada lunes a las 09:00"
    assert created.prompt == "Resúmeme las decisiones pendientes"
    assert created.title == "Lunes"

    loaded = await routine_store.get(created.id)
    assert loaded == created
    assert await routine_store.get("no-existe") is None


async def test_list_routines_is_newest_first_and_archive_stays_readable(routine_store):
    assert await routine_store.list_routines() == []

    first = await _create(routine_store, title="Primera")
    await asyncio.sleep(0.05)
    second = await _create(routine_store, title="Segunda", status="paused")
    await asyncio.sleep(0.05)
    third = await _create(
        routine_store, title="Tercera", status="pending_activation", created_by="assistant",
    )
    assert third.created_at > second.created_at > first.created_at

    assert [item.id for item in await routine_store.list_routines()] == [
        third.id, second.id, first.id,
    ]

    archived = await routine_store.set_status(third.id, "archived")
    assert archived is not None
    assert archived.status == "archived"
    assert [item.id for item in await routine_store.list_routines()] == [second.id, first.id]

    saved = await routine_store.get(third.id)
    assert saved is not None
    assert saved.status == "archived"
    assert saved.title == "Tercera"
    assert await routine_store.set_status("no-existe", "active") is None


async def test_second_start_run_returns_none_until_finish(routine_store):
    routine = await _create(routine_store)
    other = await _create(routine_store, title="Otra")
    started = datetime(2026, 11, 24, 9, 0, tzinfo=_MEXICO)

    assert await routine_store.start_run("no-existe", started) is None

    first = await routine_store.start_run(routine.id, started)
    assert first is not None
    assert first.status == "running"
    assert first.finished_at is None
    assert first.output == ""
    assert first.routine_id == routine.id
    assert first.started_at.tzinfo is not None
    assert first.started_at == started

    assert await routine_store.start_run(routine.id, started) is None
    assert [item.id for item in await routine_store.list_runs(routine.id)] == [first.id]
    saved = await routine_store.get(routine.id)
    assert saved is not None and saved.runs_count == 0

    other_run = await routine_store.start_run(other.id, started)
    assert other_run is not None
    assert await routine_store.start_run(other.id, started) is None

    finished_at = datetime(2026, 11, 24, 15, 5, tzinfo=timezone.utc)
    nxt = datetime(2026, 12, 1, 9, 0, tzinfo=_MEXICO)
    closed = await routine_store.finish_run(
        first.id,
        status="ok",
        output="Resumen listo.",
        finished_at=finished_at,
        next_run_at=nxt,
    )
    assert closed is not None and closed.status == "ok"

    again_at = datetime(2026, 11, 24, 16, 0, tzinfo=timezone.utc)
    second = await routine_store.start_run(routine.id, again_at)
    assert second is not None
    assert second.id != first.id
    assert await routine_store.start_run(routine.id, again_at) is None
    assert [item.id for item in await routine_store.list_runs(routine.id)] == [second.id, first.id]
    assert [item.id for item in await routine_store.list_runs(other.id)] == [other_run.id]


async def test_finish_run_updates_the_routine_without_changing_its_status(routine_store):
    routine = await _create(routine_store, status="active")
    started = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)
    run = await routine_store.start_run(routine.id, started)
    assert run is not None

    missing = await routine_store.finish_run(
        "no-existe",
        status="error",
        output="nada",
        finished_at=started,
        next_run_at=None,
    )
    assert missing is None

    finished_at = datetime(2026, 11, 24, 15, 5, tzinfo=_MEXICO)
    nxt = datetime(2026, 12, 1, 9, 0, tzinfo=_MEXICO)
    closed = await routine_store.finish_run(
        run.id,
        status="error",
        output="No se pudo completar la rutina.",
        finished_at=finished_at,
        next_run_at=nxt,
    )
    assert closed is not None
    assert closed.status == "error"
    assert closed.output == "No se pudo completar la rutina."
    assert closed.finished_at is not None
    assert closed.finished_at.tzinfo is not None
    assert closed.finished_at == finished_at

    saved = await routine_store.get(routine.id)
    assert saved is not None
    assert saved.status == "active"
    assert saved.runs_count == 1
    assert saved.last_run_at is not None
    assert saved.last_run_at.tzinfo is not None
    assert saved.last_run_at == finished_at
    assert saved.next_run_at == nxt

    later = datetime(2026, 11, 24, 16, 0, tzinfo=timezone.utc)
    again = await routine_store.finish_run(
        run.id,
        status="ok",
        output="no debe guardarse",
        finished_at=later,
        next_run_at=None,
    )
    assert again is None
    saved = await routine_store.get(routine.id)
    assert saved is not None
    assert saved.runs_count == 1
    assert saved.status == "active"
    assert saved.last_run_at == finished_at
    assert saved.next_run_at == nxt
    runs = await routine_store.list_runs(routine.id)
    assert len(runs) == 1
    assert runs[0].status == "error"
    assert runs[0].output == "No se pudo completar la rutina."


async def test_list_runs_is_newest_first(routine_store):
    routine = await _create(routine_store)
    assert await routine_store.list_runs(routine.id) == []
    assert await routine_store.list_runs("no-existe") == []

    first_at = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)
    second_at = datetime(2026, 11, 24, 16, 0, tzinfo=timezone.utc)
    done = datetime(2026, 11, 24, 15, 1, tzinfo=timezone.utc)
    first = await routine_store.start_run(routine.id, first_at)
    assert first is not None
    await routine_store.finish_run(
        first.id, status="ok", output="primera", finished_at=done, next_run_at=_DUE,
    )
    second = await routine_store.start_run(routine.id, second_at)
    assert second is not None

    runs = await routine_store.list_runs(routine.id)
    assert [item.id for item in runs] == [second.id, first.id]
    assert runs[0].started_at == second_at
    assert runs[1].started_at == first_at
    assert runs[0].status == "running"
    assert runs[1].status == "ok"
    assert runs[1].output == "primera"


async def test_list_due_skips_pending_running_and_future_routines(routine_store):
    at = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)
    early_at = datetime(2026, 11, 24, 8, 0, tzinfo=timezone.utc)
    late_at = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
    future_at = datetime(2026, 11, 24, 18, 1, tzinfo=timezone.utc)
    # 09:00 en Ciudad de México son las 15:00 UTC.
    mexico_at = datetime(2026, 11, 24, 9, 0, tzinfo=_MEXICO)

    pending = await _create(
        routine_store, title="Pendiente", status="pending_activation", next_run_at=early_at,
    )
    paused = await _create(routine_store, title="En pausa", status="paused", next_run_at=early_at)
    archived = await _create(routine_store, title="Archivada", next_run_at=early_at)
    await routine_store.set_status(archived.id, "archived")
    future = await _create(routine_store, title="Futura", next_run_at=future_at)
    unscheduled = await _create(routine_store, title="Sin hora", next_run_at=None)
    running = await _create(routine_store, title="En curso", next_run_at=early_at)
    early = await _create(routine_store, title="Temprana", next_run_at=early_at)
    late = await _create(routine_store, title="Tarde", next_run_at=late_at)
    mexico = await _create(routine_store, title="México", next_run_at=mexico_at)

    opened = await routine_store.start_run(running.id, early_at)
    assert opened is not None

    due_ids = [item.id for item in await routine_store.list_due(at)]
    assert due_ids == [early.id, late.id, mexico.id]
    assert pending.id not in due_ids
    assert paused.id not in due_ids
    assert archived.id not in due_ids
    assert future.id not in due_ids
    assert unscheduled.id not in due_ids
    assert running.id not in due_ids

    before_mexico = datetime(2026, 11, 24, 14, 59, tzinfo=timezone.utc)
    at_mexico = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)
    assert mexico.id not in [item.id for item in await routine_store.list_due(before_mexico)]
    visible_at_mexico = [item.id for item in await routine_store.list_due(at_mexico)]
    assert visible_at_mexico == [early.id, late.id, mexico.id]

    await routine_store.finish_run(
        opened.id, status="ok", output="listo", finished_at=at, next_run_at=early_at,
    )
    assert [item.id for item in await routine_store.list_due(at)] == [
        running.id, early.id, late.id, mexico.id,
    ]


@pytest.mark.integration
async def test_two_concurrent_start_runs_open_exactly_one():
    engine, store = await _open_postgres()
    try:
        routine = await _create(store)
        started = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
        # Dos sesiones a la vez: el índice único deja pasar solo una ejecución en curso.
        first, second = await asyncio.gather(
            store.start_run(routine.id, started),
            store.start_run(routine.id, started),
        )
        opened = [run for run in (first, second) if run is not None]
        assert len(opened) == 1
        assert opened[0].status == "running"
        assert opened[0].routine_id == routine.id
        runs = await store.list_runs(routine.id)
        assert [item.id for item in runs] == [opened[0].id]
        assert runs[0].status == "running"
    finally:
        await engine.dispose()
