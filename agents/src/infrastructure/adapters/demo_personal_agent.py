import asyncio
from collections.abc import AsyncIterator

from agents.src.application.assistant.toolbox import AssistantToolbox
from agents.src.application.ports.personal_agent import (
    AgentEvent,
    Conversation,
    PersonalAgentPort,
    TextDelta,
    ToolFinished,
    ToolStarted,
    TurnFinished,
)


class DemoPersonalAgent(PersonalAgentPort):
    """
    Asistente de demostración (F7-T3): se usa cuando no hay credencial de Claude configurada.

    No razona. Hace una búsqueda REAL en la memoria con el texto recibido y devuelve lo que
    encontró con un texto fijo, emitiendo los mismos eventos que el asistente real — así la
    interfaz, el streaming y el paso por el Gateway se pueden probar de punta a punta sin API key,
    y nadie confunde esto con una respuesta de Claude: el propio texto lo dice.
    """
    model_name = "demo"

    def __init__(self, toolbox: AssistantToolbox, chunk_delay: float = 0.012):
        self._toolbox = toolbox
        self._chunk_delay = chunk_delay

    async def stream_reply(self, conversation: Conversation, user_text: str) -> AsyncIterator[AgentEvent]:
        tool_id = f"demo_{len(conversation.transcript)}"
        spec = self._toolbox.resolve("search_memory")
        yield ToolStarted(id=tool_id, name="search_memory", label=spec.label, input={"query": user_text})
        outcome = await self._toolbox.execute("search_memory", {"query": user_text})
        yield ToolFinished(
            id=tool_id, name="search_memory", ok=not outcome.is_error,
            summary=outcome.summary, sources=outcome.sources,
        )

        if outcome.is_error:
            findings = "No pude consultar tu memoria: el servicio de memoria no respondió."
        elif outcome.sources:
            titles = "\n".join(f"- «{source['title']}»" for source in outcome.sources)
            findings = f"Busqué tu mensaje en la memoria y esto es lo más cercano que encontré:\n\n{titles}"
        else:
            findings = "Busqué tu mensaje en la memoria y no encontré nada relacionado todavía."

        reply = (
            "**Modo demostración.** Este servicio no tiene una API key de Claude configurada, "
            "así que no puedo razonar ni redactar una respuesta a lo que escribiste.\n\n"
            f"{findings}\n\n"
            "Para activar el asistente real, agrega `ANTHROPIC_API_KEY` al archivo `.env` y "
            "reinicia el servicio de agentes."
        )

        # Se emite en trozos pequeños para que la interfaz ejercite el mismo camino de streaming.
        for start in range(0, len(reply), 6):
            yield TextDelta(reply[start:start + 6])
            if self._chunk_delay:
                await asyncio.sleep(self._chunk_delay)

        tools_used = [{
            "id": tool_id, "name": "search_memory", "ok": not outcome.is_error,
            "summary": outcome.summary, "sources": outcome.sources,
        }]
        conversation.transcript.append({"role": "user", "text": user_text})
        conversation.transcript.append({
            "role": "assistant", "text": reply, "tools": tools_used, "stop_reason": "end_turn",
        })
        yield TurnFinished(stop_reason="end_turn", model=self.model_name, usage={})
