"""
F7-T1: `AnthropicLlm` deja que el Planner y el Reviewer (que hablan con `LlmPort`) corran sobre
Claude sin cambios: mismo contrato de texto/JSON que el adaptador de Ollama.
"""
import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from agents.src.domain.planner.llm_planner import LlmPlanner
from agents.src.infrastructure.adapters.anthropic_llm import AnthropicLlm, extract_json


class FakeClient:
    def __init__(self, text="ok", stop_reason="end_turn", error=None):
        self.requests: list[dict] = []
        self._text, self._stop_reason, self._error = text, stop_reason, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    async def _create(self, **params):
        self.requests.append(params)
        if self._error:
            raise self._error
        return SimpleNamespace(
            stop_reason=self._stop_reason,
            # Con razonamiento adaptativo la respuesta puede empezar con un bloque `thinking`.
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=self._text)],
        )


@pytest.mark.parametrize(("raw", "expected"), [
    ('{"approved": true}', {"approved": True}),
    ('```json\n{"approved": true}\n```', {"approved": True}),
    ('Aquí está el plan:\n{"steps": [{"step_id": 1}]}\nEspero que sirva.', {"steps": [{"step_id": 1}]}),
    ('Nota {no es json} y luego {"ok": 1}', {"ok": 1}),
    ('[1, 2, 3]', [1, 2, 3]),
])
def test_extract_json_tolerates_what_models_wrap_around_it(raw, expected):
    assert json.loads(extract_json(raw)) == expected


def test_extract_json_returns_the_text_untouched_when_there_is_no_json():
    assert extract_json("no hay nada aquí") == "no hay nada aquí"


async def test_generate_sends_a_sonnet_request_and_reads_text_by_block_type():
    client = FakeClient(text="Hola")
    result = await AnthropicLlm(client).generate("Saluda", system_instruction="Eres breve.")

    assert result == "Hola"
    request = client.requests[0]
    assert request["model"] == "claude-sonnet-5-5"
    assert request["system"] == "Eres breve."
    assert request["messages"] == [{"role": "user", "content": "Saluda"}]
    assert request["output_config"] == {"effort": "medium"}
    assert request["fallbacks"] == "default"
    # Nada que este modelo rechace: sin presupuestos de razonamiento, sin sampling, sin prefill.
    assert not {"thinking", "temperature", "top_p", "top_k", "tool_choice"} & set(request)
    assert request["messages"][-1]["role"] == "user"


async def test_json_mode_is_requested_by_instruction_and_the_reply_is_cleaned():
    client = FakeClient(text='```json\n{"approved": true, "feedback": "bien"}\n```')
    result = await AnthropicLlm(client).generate("Evalúa", json_mode=True)

    assert json.loads(result) == {"approved": True, "feedback": "bien"}
    assert "JSON válido" in client.requests[0]["system"]


async def test_chat_moves_system_messages_to_the_system_parameter():
    client = FakeClient()
    await AnthropicLlm(client).chat([
        {"role": "system", "content": "Eres el planner."},
        {"role": "user", "content": "Hola"},
    ])

    request = client.requests[0]
    assert request["system"] == "Eres el planner."
    assert request["messages"] == [{"role": "user", "content": "Hola"}]


async def test_fallbacks_can_be_switched_off():
    client = FakeClient()
    await AnthropicLlm(client, fallbacks_enabled=False).generate("Hola")
    assert "fallbacks" not in client.requests[0] and "betas" not in client.requests[0]


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
async def test_incomplete_answers_raise_instead_of_returning_half_a_reply(stop_reason):
    with pytest.raises(RuntimeError):
        await AnthropicLlm(FakeClient(stop_reason=stop_reason)).generate("Hola")


async def test_api_errors_surface_as_runtime_error_like_the_other_adapters():
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.RateLimitError("429", response=httpx2.Response(429, request=request), body=None)

    with pytest.raises(RuntimeError, match="Claude"):
        await AnthropicLlm(FakeClient(error=error)).generate("Hola")


async def test_the_planner_runs_on_claude_unchanged():
    plan = {
        "plan_id": "018b10f8-e1a5-7b18-b2a6-382a93414902", "goal": "Revisar Traefik",
        "steps": [{
            "step_id": 1, "task": "Buscar la nota", "capability_name": "search_knowledge",
            "expected_output": "La nota", "status": "pending",
        }],
    }
    client = FakeClient(text=f"Claro, este es el plan:\n```json\n{json.dumps(plan)}\n```")

    response = await LlmPlanner(AnthropicLlm(client)).plan("Revisar Traefik", "sin contexto", [])

    assert response.steps[0].capability_name == "search_knowledge"
