"""
Rutinas programadas: el asistente las propone y quedan pendientes; solo corren cuando la
persona las activa. A su hora (o al pulsar ejecutar) son un turno del asistente.
"""
import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from agents.src import main as agents_main
from agents.src.application.assistant.routines import (
    RoutineRunner,
    ScheduleError,
    compute_next_run,
    describe_schedule,
    normalize_schedule,
    register_routine,
)
from agents.src.application.assistant.toolbox import TOOL_SPECS, AssistantToolbox
from agents.src.application.ports.personal_agent import (
    PersonalAgentPort,
    TextDelta,
    TurnFailed,
    TurnFinished,
)
from agents.src.infrastructure.adapters.demo_personal_agent import DemoPersonalAgent
from agents.src.infrastructure.adapters.in_memory_conversation_store import (
    InMemoryConversationStore,
)
from agents.src.infrastructure.adapters.in_memory_routine_store import InMemoryRoutineStore
from agents.tests.test_assistant_toolbox import FakeMemoryGateway

_PAST = datetime(2020, 1, 1, tzinfo=timezone.utc)


def _demo() -> DemoPersonalAgent:
    return DemoPersonalAgent(AssistantToolbox(FakeMemoryGateway()), chunk_delay=0)


async def _routine(store, *, status="active", title="Decisiones del lunes", prompt="Resúmeme las decisiones pendientes"):
    created_by = "assistant" if status == "pending_activation" else "user"
    return await register_routine(
        store,
        title=title,
        prompt=prompt,
        schedule="0 9 * * 1",
        timezone_name="America/Mexico_City",
        configured_timezone="America/Mexico_City",
        status=status,
        created_by=created_by,
    )


@pytest.mark.parametrize(("expr", "expected"), [
    ("0 9 * * 1", "cada lunes a las 09:00"),
    ("30 8 * * *", "todos los días a las 08:30"),
    ("0 9 1 * *", "el día 1 de cada mes a las 09:00"),
    ("15 18 * * 1,3,5", "cada lunes, miércoles y viernes a las 18:15"),
    ("0 9 * * 1-5", "de lunes a viernes a las 09:00"),
    ("45 7 15 * *", "el día 15 de cada mes a las 07:45"),
    ("0 9 * * 0", "cada domingo a las 09:00"),
    ("0 9 * * 7", "cada domingo a las 09:00"),
])
def test_describe_schedule_in_spanish(expr, expected):
    assert describe_schedule(expr) == expected


@pytest.mark.parametrize("expr", ["*/15 * * * *", "0 9 * 1 *", "0 9 1 * 1"])
def test_unrecognized_schedule_is_quoted_instead_of_guessed(expr):
    assert describe_schedule(expr) == f"según la expresión cron {expr}"


def test_next_run_is_computed_in_the_given_timezone():
    # Lunes 23 nov 2026, 14:30 UTC = 08:30 en Ciudad de México: ese mismo lunes a las 9.
    # En UTC las 9:00 de ese lunes ya pasaron, así que la siguiente es el lunes 30.
    after = datetime(2026, 11, 23, 14, 30, tzinfo=ZoneInfo("UTC"))
    mexico = compute_next_run("0 9 * * 1", "America/Mexico_City", after=after)
    utc = compute_next_run("0 9 * * 1", "UTC", after=after)

    assert mexico == datetime(2026, 11, 23, 9, 0, tzinfo=ZoneInfo("America/Mexico_City"))
    assert utc == datetime(2026, 11, 30, 9, 0, tzinfo=ZoneInfo("UTC"))


@pytest.mark.parametrize("expr", ["mañana a las 9", "0 9 * *", "99 9 * * 1", "@daily", "0 9 * * 1 1"])
def test_invalid_cron_is_rejected(expr):
    with pytest.raises(ScheduleError):
        normalize_schedule(expr)


def test_create_routine_tool_tells_the_model_the_person_must_activate_it():
    names = [spec.name for spec in TOOL_SPECS]
    assert names[0] == "search_memory"
    assert names[-2:] == ["create_routine", "list_routines"]
    description = next(spec.description for spec in TOOL_SPECS if spec.name == "create_routine")
    assert "pendiente" in description
    assert "Agentes → Rutinas" in description
    assert "Díselo" in description


async def test_tool_without_a_store_explains_that_routines_are_unavailable():
    box = AssistantToolbox(FakeMemoryGateway())
    created = await box.execute("create_routine", {
        "title": "Lunes", "prompt": "Resume las decisiones", "schedule": "0 9 * * 1",
    })
    listed = await box.execute("list_routines", {})

    assert created.is_error and listed.is_error
    assert created.content == "Las rutinas no están disponibles en este servicio."
    assert listed.content == created.content


async def test_tool_rejects_an_invalid_cron_without_saving():
    store = InMemoryRoutineStore()
    box = AssistantToolbox(FakeMemoryGateway(), routine_store=store)

    outcome = await box.execute("create_routine", {
        "title": "Lunes", "prompt": "Resume las decisiones", "schedule": "mañana a las 9",
    })

    assert outcome.is_error
    assert outcome.summary == "Programación no válida"
    assert "cinco campos" in outcome.content
    assert await store.list_routines() == []


async def test_tool_creates_a_pending_routine_that_does_not_run_when_overdue():
    store = InMemoryRoutineStore()
    box = AssistantToolbox(FakeMemoryGateway(), routine_store=store)
    outcome = await box.execute("create_routine", {
        "title": "Decisiones del lunes",
        "prompt": "Resúmeme las decisiones pendientes",
        "schedule": "0 9 * * 1",
        "timezone": "America/Mexico_City",
    })

    assert not outcome.is_error
    assert outcome.summary == "Rutina pendiente: Decisiones del lunes"
    routine = (await store.list_routines())[0]
    assert routine.status == "pending_activation"
    assert routine.created_by == "assistant"
    assert routine.schedule_description == "cada lunes a las 09:00"

    routine.next_run_at = _PAST
    runner = RoutineRunner(store, InMemoryConversationStore(), _demo())
    assert await store.list_due(datetime.now(timezone.utc)) == []
    assert await runner.run(routine.id) is None
    assert await store.list_runs(routine.id) == []

    listed = await box.execute("list_routines", {})
    assert "Decisiones del lunes" in listed.content
    assert "cada lunes a las 09:00" in listed.content


async def test_activated_routine_runs_with_the_demo_agent_and_saves_the_text():
    store = InMemoryRoutineStore()
    conversations = InMemoryConversationStore()
    routine = await _routine(store, status="pending_activation")
    routine.next_run_at = _PAST
    await store.set_status(routine.id, "active")

    run = await RoutineRunner(store, conversations, _demo()).run(routine.id)

    assert run is not None
    assert run.status == "ok"
    assert "Modo demostración" in run.output
    assert run.finished_at is not None
    saved = await store.get(routine.id)
    assert saved is not None
    assert saved.status == "active"
    assert saved.runs_count == 1
    assert saved.last_run_at == run.finished_at
    conversation = next(iter(conversations._conversations.values()))
    assert conversation.transcript[0] == {"role": "user", "text": routine.prompt}


async def test_a_failed_turn_is_stored_and_the_routine_stays_active_with_a_new_time():
    store = InMemoryRoutineStore()
    routine = await _routine(store)
    routine.next_run_at = _PAST

    class FailingAgent(PersonalAgentPort):
        model_name = "fallo"

        async def stream_reply(self, conversation, user_text):
            yield TextDelta("texto que no debe guardarse")
            yield TurnFailed(message="No se pudo completar la respuesta.")

    run = await RoutineRunner(store, InMemoryConversationStore(), FailingAgent()).run(routine.id)

    assert run is not None
    assert run.status == "error"
    assert run.output == "No se pudo completar la respuesta."
    saved = await store.get(routine.id)
    assert saved is not None
    assert saved.status == "active"
    assert saved.runs_count == 1
    assert saved.next_run_at is not None
    assert saved.next_run_at > datetime.now(timezone.utc)


async def test_archive_hides_the_routine_from_the_list():
    store = InMemoryRoutineStore()
    routine = await _routine(store)
    await store.set_status(routine.id, "archived")

    assert await store.list_routines() == []
    saved = await store.get(routine.id)
    assert saved is not None and saved.status == "archived"


async def test_a_second_run_does_not_start_while_one_is_in_progress():
    store = InMemoryRoutineStore()
    routine = await _routine(store)

    class GateAgent(PersonalAgentPort):
        model_name = "demo"

        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def stream_reply(self, conversation, user_text):
            self.started.set()
            await self.release.wait()
            yield TextDelta("listo")
            yield TurnFinished(stop_reason="end_turn", model=self.model_name, usage={})

    agent = GateAgent()
    runner = RoutineRunner(store, InMemoryConversationStore(), agent)
    first = asyncio.create_task(runner.run(routine.id))
    await agent.started.wait()

    assert await runner.run(routine.id) is None
    agent.release.set()
    finished = await first

    assert finished is not None and finished.status == "ok"
    assert len(await store.list_runs(routine.id)) == 1


async def test_scheduler_runs_only_active_routines_that_are_due(monkeypatch):
    store = InMemoryRoutineStore()
    monkeypatch.setattr(agents_main, "routine_store", store)
    monkeypatch.setattr(agents_main, "conversation_store", InMemoryConversationStore())
    monkeypatch.setattr(agents_main, "get_personal_agent", lambda http_client=None: _demo())
    pending = await _routine(store, status="pending_activation", title="Pendiente")
    active = await _routine(store, title="Activa")
    pending.next_run_at = _PAST
    active.next_run_at = _PAST

    await agents_main._execute_due_routines()

    assert await store.list_runs(pending.id) == []
    runs = await store.list_runs(active.id)
    assert len(runs) == 1 and runs[0].status == "ok" and "Modo demostración" in runs[0].output
    await agents_main._execute_due_routines()
    assert len(await store.list_runs(active.id)) == 1


@pytest.fixture
def routine_store(monkeypatch):
    store = InMemoryRoutineStore()
    monkeypatch.setattr(agents_main, "routine_store", store)
    monkeypatch.setattr(agents_main, "conversation_store", InMemoryConversationStore())
    monkeypatch.setattr(agents_main, "get_personal_agent", lambda http_client=None: _demo())
    monkeypatch.setattr(agents_main.settings, "ROUTINES_ENABLED", False)
    return store


@pytest.fixture
def client(routine_store):
    return TestClient(agents_main.app)


def test_api_rejects_invalid_cron_and_unknown_routines(client):
    rejected = client.post("/api/v1/agents/routines", json={
        "title": "Mala", "prompt": "Haz algo concreto", "schedule": "mañana a las 9",
    })
    assert rejected.status_code == 422
    assert "cinco campos" in rejected.json()["detail"]

    zone = client.post("/api/v1/agents/routines", json={
        "title": "Mala zona", "prompt": "Haz algo concreto",
        "schedule": "0 9 * * 1", "timezone": "No/Existe",
    })
    assert zone.status_code == 422
    assert "zona horaria" in zone.json()["detail"]

    missing = client.post("/api/v1/agents/routines/no-existe/activate")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "No encontramos esa rutina."
    assert client.get("/api/v1/agents/routines/no-existe/runs").status_code == 404


def test_api_creates_an_active_routine_and_runs_it_on_demand(client):
    created = client.post("/api/v1/agents/routines", json={
        "title": "Decisiones del lunes",
        "prompt": "Resúmeme las decisiones pendientes",
        "schedule": "0 9 * * 1",
        "timezone": "America/Mexico_City",
    })
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "active"
    assert body["created_by"] == "user"
    assert body["schedule_description"] == "cada lunes a las 09:00"
    assert body["timezone"] == "America/Mexico_City"
    routine_id = body["id"]

    listed = client.get("/api/v1/agents/routines")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["routines"]] == [routine_id]

    paused = client.post(f"/api/v1/agents/routines/{routine_id}/pause")
    assert paused.status_code == 200 and paused.json()["status"] == "paused"
    assert len(client.get("/api/v1/agents/routines").json()["routines"]) == 1

    active = client.post(f"/api/v1/agents/routines/{routine_id}/activate")
    assert active.json()["status"] == "active"

    ran = client.post(f"/api/v1/agents/routines/{routine_id}/run")
    assert ran.status_code == 202
    runs = client.get(f"/api/v1/agents/routines/{routine_id}/runs").json()["runs"]
    assert runs[0]["status"] == "ok"
    assert "Modo demostración" in runs[0]["output"]

    again = client.post(f"/api/v1/agents/routines/{routine_id}/run")
    assert again.status_code == 202
    newest_first = client.get(f"/api/v1/agents/routines/{routine_id}/runs").json()["runs"]
    assert len(newest_first) == 2
    assert newest_first[0]["started_at"] >= newest_first[1]["started_at"]

    archived = client.post(f"/api/v1/agents/routines/{routine_id}/archive")
    assert archived.json()["status"] == "archived"
    assert client.get("/api/v1/agents/routines").json()["routines"] == []
    assert client.get(f"/api/v1/agents/routines/{routine_id}/runs").status_code == 200


def test_api_refuses_to_run_a_routine_that_is_still_pending(client, routine_store):
    routine = asyncio.run(_routine(routine_store, status="pending_activation"))

    response = client.post(f"/api/v1/agents/routines/{routine.id}/run")

    assert response.status_code == 409
    assert response.json()["detail"] == "Activa la rutina para que pueda ejecutarse."
    assert asyncio.run(routine_store.list_runs(routine.id)) == []


def test_lifespan_starts_the_scheduler_and_cancels_it_on_shutdown(monkeypatch):
    monkeypatch.setattr(agents_main.settings, "ROUTINES_ENABLED", True)
    monkeypatch.setattr(agents_main.settings, "ROUTINES_TICK_SECONDS", 3600)

    with TestClient(agents_main.app):
        task = agents_main._routines_task
        assert task is not None and not task.done()

    assert agents_main._routines_task is None
    assert task.cancelled()


def test_lifespan_does_not_start_the_scheduler_when_it_is_disabled(monkeypatch):
    monkeypatch.setattr(agents_main.settings, "ROUTINES_ENABLED", False)

    with TestClient(agents_main.app):
        assert agents_main._routines_task is None
