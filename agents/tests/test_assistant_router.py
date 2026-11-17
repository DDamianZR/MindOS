"""
F7-T4: el endpoint del asistente responde en streaming (SSE), mantiene la conversación entre
mensajes y elige el proveedor según la configuración — Claude si hay credencial, demostración
si no (nunca un error opaco por falta de API key).
"""
import json

import pytest
from fastapi.testclient import TestClient

from agents.src import main as agents_main
from agents.src.api import assistant_router
from agents.src.application.assistant.toolbox import AssistantToolbox
from agents.src.infrastructure.adapters.claude_personal_agent import ClaudePersonalAgent
from agents.src.infrastructure.adapters.demo_personal_agent import DemoPersonalAgent
from agents.src.infrastructure.adapters.in_memory_conversation_store import (
    InMemoryConversationStore,
)
from agents.tests.test_assistant_toolbox import FakeMemoryGateway


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for chunk in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in chunk.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(agents_main, "conversation_store", InMemoryConversationStore())
    monkeypatch.setattr(assistant_router, "_busy_conversations", set())
    agents_main.app.dependency_overrides[agents_main.get_personal_agent] = (
        lambda: DemoPersonalAgent(AssistantToolbox(FakeMemoryGateway()), chunk_delay=0)
    )
    yield TestClient(agents_main.app)
    agents_main.app.dependency_overrides.clear()


def test_chat_streams_a_full_turn_as_server_sent_events(client):
    resp = client.post("/api/v1/agents/assistant/chat", json={"message": "¿Qué base de datos elegí?"})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.text)
    kinds = [kind for kind, _ in events]
    assert kinds[0] == "conversation" and kinds[1:3] == ["tool_start", "tool_end"] and kinds[-1] == "done"
    assert set(kinds[3:-1]) == {"text"}

    tool_end = events[2][1]
    assert tool_end["ok"] is True and tool_end["sources"][0]["title"] == "Decisión: usar Postgres"
    text = "".join(data["text"] for kind, data in events if kind == "text")
    assert "Modo demostración" in text and "«Decisión: usar Postgres»" in text


def test_conversation_continues_across_messages_and_can_be_restored(client):
    first = _parse_sse(client.post("/api/v1/agents/assistant/chat", json={"message": "Hola"}).text)
    conversation_id = first[0][1]["conversation_id"]

    second = _parse_sse(client.post(
        "/api/v1/agents/assistant/chat", json={"message": "¿Y Traefik?", "conversation_id": conversation_id},
    ).text)
    assert second[0][1]["conversation_id"] == conversation_id

    restored = client.get(f"/api/v1/agents/assistant/conversations/{conversation_id}")
    assert restored.status_code == 200
    messages = restored.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[2]["text"] == "¿Y Traefik?"
    assert messages[3]["tools"][0]["name"] == "search_memory"


def test_unknown_conversation_is_a_clear_404_not_a_silent_new_conversation(client):
    resp = client.post(
        "/api/v1/agents/assistant/chat", json={"message": "Hola", "conversation_id": "no-existe"},
    )
    assert resp.status_code == 404
    assert "Empieza una nueva" in resp.json()["detail"]


def test_empty_message_is_rejected(client):
    assert client.post("/api/v1/agents/assistant/chat", json={"message": ""}).status_code == 422


def test_a_second_message_while_the_first_is_still_streaming_is_rejected(client, monkeypatch):
    first = _parse_sse(client.post("/api/v1/agents/assistant/chat", json={"message": "Hola"}).text)
    conversation_id = first[0][1]["conversation_id"]
    monkeypatch.setattr(assistant_router, "_busy_conversations", {conversation_id})

    resp = client.post(
        "/api/v1/agents/assistant/chat", json={"message": "Otra", "conversation_id": conversation_id},
    )
    assert resp.status_code == 409


def test_unexpected_failure_mid_stream_arrives_as_an_error_event(client):
    class ExplodingAgent(DemoPersonalAgent):
        async def stream_reply(self, conversation, user_text):
            raise RuntimeError("se rompió algo")
            yield  # pragma: no cover

    agents_main.app.dependency_overrides[agents_main.get_personal_agent] = (
        lambda: ExplodingAgent(AssistantToolbox(FakeMemoryGateway()))
    )
    events = _parse_sse(client.post("/api/v1/agents/assistant/chat", json={"message": "Hola"}).text)

    assert [kind for kind, _ in events] == ["conversation", "error"]
    assert "se rompió algo" not in events[1][1]["message"], "los detalles internos no llegan al navegador"

    # Y la conversación no queda bloqueada para el siguiente intento.
    assert assistant_router._busy_conversations == set()


def test_status_reports_demo_mode(client):
    body = client.get("/api/v1/agents/assistant/status").json()
    assert body["provider"] == "demo" and body["model"] == "demo"
    assert "search_memory" in body["tools"]


# --- Selección de proveedor ---

@pytest.mark.parametrize(("provider", "api_key", "env", "expected"), [
    ("auto", "sk-ant-x", "development", "anthropic"),
    ("auto", "", "development", "mock"),
    ("auto", "", "production", "ollama"),
    ("ollama", "sk-ant-x", "production", "ollama"),
    ("anthropic", "", "development", "anthropic"),
])
def test_provider_resolution(monkeypatch, provider, api_key, env, expected):
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(agents_main.settings, "LLM_PROVIDER", provider)
    monkeypatch.setattr(agents_main.settings, "ANTHROPIC_API_KEY", api_key)
    monkeypatch.setattr(agents_main.settings, "MINDOS_ENV", env)

    assert agents_main.resolve_llm_provider() == expected


def test_with_a_credential_the_assistant_is_claude_sonnet(monkeypatch):
    monkeypatch.setattr(agents_main.settings, "LLM_PROVIDER", "auto")
    monkeypatch.setattr(agents_main.settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(agents_main, "_anthropic_client", None)

    agent = agents_main.get_personal_agent(http_client=None)

    assert isinstance(agent, ClaudePersonalAgent)
    assert agent.model_name == "claude-sonnet-5-5"


def test_without_a_credential_the_assistant_falls_back_to_demo(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(agents_main.settings, "LLM_PROVIDER", "auto")
    monkeypatch.setattr(agents_main.settings, "ANTHROPIC_API_KEY", "")

    assert isinstance(agents_main.get_personal_agent(http_client=None), DemoPersonalAgent)
