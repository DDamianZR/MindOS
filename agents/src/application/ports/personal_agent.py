from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Conversation:
    """
    Una conversación con el asistente personal (F7-T3).

    `messages` es el historial en el formato del proveedor del modelo y es **solo-anexar**: los
    turnos del asistente se guardan tal como llegaron (incluidos sus bloques de razonamiento),
    porque el proveedor verifica que nada anterior haya cambiado al reenviarlos. `transcript`
    es la versión para pintar en pantalla (lo que un cliente necesita para restaurar el chat).
    """
    id: str
    started_at: str
    messages: list[Any] = field(default_factory=list)
    transcript: list[dict[str, Any]] = field(default_factory=list)


# --- Eventos que emite un turno del asistente (se serializan tal cual a SSE) ---

@dataclass
class TextDelta:
    text: str
    type: str = "text"


@dataclass
class ThinkingDelta:
    """Resumen del razonamiento o nota de progreso entre herramientas (nunca el razonamiento crudo)."""
    text: str
    type: str = "thinking"


@dataclass
class ToolStarted:
    id: str
    name: str
    label: str
    input: dict[str, Any]
    type: str = "tool_start"


@dataclass
class ToolFinished:
    id: str
    name: str
    ok: bool
    summary: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    type: str = "tool_end"


@dataclass
class TurnRestarted:
    """El turno en curso se reintenta: el cliente debe descartar el texto parcial que ya pintó."""
    type: str = "restart"


@dataclass
class TurnFinished:
    stop_reason: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    type: str = "done"


@dataclass
class TurnFailed:
    message: str
    type: str = "error"


AgentEvent = (
    TextDelta | ThinkingDelta | ToolStarted | ToolFinished | TurnRestarted | TurnFinished | TurnFailed
)


def event_to_dict(event: AgentEvent) -> dict[str, Any]:
    return asdict(event)


class PersonalAgentPort(ABC):
    """
    Puerto del asistente personal: dado el historial y un mensaje nuevo, produce el turno de
    respuesta como un flujo de eventos (texto, uso de herramientas, cierre). El adaptador es
    dueño del bucle de herramientas y de mantener `conversation.messages` consistente: si el
    turno falla, lo deja como estaba antes de empezar.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identificador del modelo que responde (para mostrarlo en la interfaz)."""

    @abstractmethod
    def stream_reply(self, conversation: Conversation, user_text: str) -> AsyncIterator[AgentEvent]:
        """Ejecuta un turno completo. Siempre termina con `TurnFinished` o `TurnFailed`."""
