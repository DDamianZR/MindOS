import json
from typing import Any

import anthropic
from mindos_common.logging import get_logger

from agents.src.application.ports.llm import LlmPort

logger = get_logger("anthropic_llm")

FALLBACK_BETA = "server-side-fallback-2026-07-01"

_JSON_INSTRUCTION = (
    "Responde únicamente con un objeto JSON válido. No añadas texto antes ni después, "
    "ni lo envuelvas en un bloque de código."
)


def extract_json(text: str) -> str:
    """
    Devuelve el primer valor JSON (objeto o lista) contenido en `text`, re-serializado.

    Los modelos actuales de Claude no admiten prefijar la respuesta del asistente para forzar
    el formato, así que el modo JSON se pide por instrucción y aquí se tolera lo que a veces
    lo acompaña (un bloque ```json o una frase suelta). Si no hay JSON, devuelve el texto
    intacto para que quien llama falle al parsear, igual que con cualquier otro adaptador.
    """
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char in "{[":
            try:
                value, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            return json.dumps(value, ensure_ascii=False)
    return text


class AnthropicLlm(LlmPort):
    """
    Adaptador de `LlmPort` sobre la API de Claude (F7-T1). Lo usan el Planner y el Reviewer del
    grafo de agentes; el asistente conversacional tiene su propio adaptador con streaming y
    herramientas (`ClaudePersonalAgent`).
    """
    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        model: str = "claude-sonnet-5-5",
        effort: str = "medium",
        max_tokens: int = 16000,
        fallbacks_enabled: bool = True,
    ):
        self._client = client
        self._model = model
        self._effort = effort
        self._max_tokens = max_tokens
        self._fallbacks_enabled = fallbacks_enabled

    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        json_mode: bool = False
    ) -> str:
        return await self._complete([{"role": "user", "content": prompt}], system_instruction, json_mode)

    async def chat(
        self,
        messages: list[dict[str, str]],
        json_mode: bool = False
    ) -> str:
        # El puerto hereda el formato de Ollama, donde el prompt de sistema viaja como un
        # mensaje más; en la API de Claude es un parámetro aparte.
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        turns = [m for m in messages if m.get("role") != "system"]
        return await self._complete(turns, "\n\n".join(system_parts) or None, json_mode)

    async def _complete(
        self, messages: list[dict[str, str]], system_instruction: str | None, json_mode: bool
    ) -> str:
        system = "\n\n".join(part for part in (system_instruction, _JSON_INSTRUCTION if json_mode else None) if part)
        params: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": messages,
            # Razonamiento adaptativo (el valor por defecto del modelo): no se envía `thinking`.
            "output_config": {"effort": self._effort},
        }
        if system:
            params["system"] = system
        if self._fallbacks_enabled:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"

        try:
            logger.debug("Enviando petición a Claude", model=self._model, json_mode=json_mode)
            response = await self._client.beta.messages.create(**params)
        except anthropic.AnthropicError as e:
            logger.error("Fallo de comunicación con la API de Claude", error=str(e), error_type=type(e).__name__)
            raise RuntimeError(f"Error de inferencia en Claude: {e}") from e

        if response.stop_reason == "refusal":
            raise RuntimeError("Claude declinó responder a esta petición por sus políticas de uso.")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("La respuesta de Claude se cortó por el límite de tokens (max_tokens).")

        # La respuesta puede empezar con bloques de razonamiento: se lee por tipo, no por posición.
        text = "".join(block.text for block in response.content if block.type == "text")
        return extract_json(text) if json_mode else text

    async def close(self) -> None:
        await self._client.close()
