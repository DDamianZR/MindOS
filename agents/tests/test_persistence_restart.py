"""
Una conversación, una rutina y el uso sobreviven a cerrar el motor y abrir otro.

Simula un reinicio del servicio: el proceso nuevo no hereda objetos, solo Postgres.
"""
import asyncio
import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from agents.src import main as agents_main
from agents.src.api import assistant_router
from agents.src.application.assistant.toolbox import AssistantToolbox
from agents.src.infrastructure.adapters.demo_personal_agent import DemoPersonalAgent
from agents.src.infrastructure.database.session import create_session_factory
from agents.src.main import build_stores
from agents.tests.test_assistant_toolbox import FakeMemoryGateway

pytestmark = pytest.mark.integration

_TRUNCATE = (
    "TRUNCATE agent_usage_turns, agent_routine_runs, "
    "agent_routines, agent_conversations CASCADE"
)


def _database_url() -> str:
    url = os.environ.get("MINDOS_TEST_AGENTS_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("MINDOS_TEST_AGENTS_DATABASE_URL no está definida")
    return url


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for chunk in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in chunk.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    return events


async def _truncate(url: str) -> None:
    engine, _session_factory = create_session_factory(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(_TRUNCATE))
    finally:
        await engine.dispose()


def _install(monkeypatch, url: str):
    built = build_stores("postgres", url)
    monkeypatch.setattr(agents_main, "conversation_store", built.conversations)
    monkeypatch.setattr(agents_main, "routine_store", built.routines)
    monkeypatch.setattr(agents_main, "usage_recorder", built.usage)
    return built


async def _dispose(client: TestClient, stores) -> None:
    # Las conexiones se abrieron en el bucle del TestClient, no en el de esta prueba.
    await asyncio.wrap_future(client.portal.start_task_soon(stores.engine.dispose))


async def test_conversation_routine_and_usage_survive_a_restart(monkeypatch):
    url = _database_url()
    await _truncate(url)

    monkeypatch.setattr(assistant_router, "_busy_conversations", set())
    agents_main.app.dependency_overrides[agents_main.get_personal_agent] = (
        lambda: DemoPersonalAgent(AssistantToolbox(FakeMemoryGateway()), chunk_delay=0)
    )
    stores = None
    try:
        with TestClient(agents_main.app) as client:
            try:
                # Arranque 1
                stores = _install(monkeypatch, url)
                first = client.post(
                    "/api/v1/agents/assistant/chat",
                    json={"message": "¿Qué base de datos elegí?"},
                )
                assert first.status_code == 200
                first_events = _parse_sse(first.text)
                assert first_events[-1][0] == "done"
                conversation_id = first_events[0][1]["conversation_id"]

                created = client.post("/api/v1/agents/routines", json={
                    "title": "Decisiones del lunes",
                    "prompt": "Resúmeme las decisiones pendientes",
                    "schedule": "0 9 * * 1",
                    "timezone": "America/Mexico_City",
                })
                assert created.status_code == 201
                routine_id = created.json()["id"]

                # Reinicio: otro motor, los objetos anteriores ya no sirven.
                await _dispose(client, stores)
                stores = _install(monkeypatch, url)

                restored = client.get(f"/api/v1/agents/assistant/conversations/{conversation_id}")
                assert restored.status_code == 200
                previous = restored.json()["messages"]
                assert [item["role"] for item in previous] == ["user", "assistant"]
                assert previous[0]["text"] == "¿Qué base de datos elegí?"

                second = client.post(
                    "/api/v1/agents/assistant/chat",
                    json={"message": "¿Y Traefik?", "conversation_id": conversation_id},
                )
                assert second.status_code == 200
                assert _parse_sse(second.text)[-1][0] == "done"

                transcript = client.get(
                    f"/api/v1/agents/assistant/conversations/{conversation_id}"
                ).json()["messages"]
                assert [item["role"] for item in transcript] == [
                    "user", "assistant", "user", "assistant",
                ]
                assert len(transcript) == 4

                listed = client.get("/api/v1/agents/routines")
                assert listed.status_code == 200
                assert [item["id"] for item in listed.json()["routines"]] == [routine_id]

                stats = client.get("/api/v1/agents/assistant/stats")
                assert stats.status_code == 200
                assert stats.json()["turns"] == 2
            finally:
                if stores is not None and stores.engine is not None:
                    await _dispose(client, stores)
    finally:
        agents_main.app.dependency_overrides.clear()
