from collections import OrderedDict
from datetime import datetime

from mindos_common.ids import new_id

from agents.src.application.ports.conversation_store import ConversationStorePort
from agents.src.application.ports.personal_agent import Conversation

_WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def describe_moment(moment: datetime) -> str:
    """Fecha legible en español, sin depender del locale del sistema (varía entre hosts)."""
    return (
        f"{_WEEKDAYS[moment.weekday()]} {moment.day} de {_MONTHS[moment.month - 1]} de {moment.year}, "
        f"{moment:%H:%M} (hora local del servidor, UTC{moment:%z})"
    )


class InMemoryConversationStore(ConversationStorePort):
    """
    Conversaciones en memoria del proceso (F7-T3), con el mismo alcance que
    `InMemoryApprovalStore`: suficiente para un Agents Service de un solo proceso. Se pierden al
    reiniciar el servicio; una implementación Postgres puede sumarse sin cambiar el contrato.

    Guarda como máximo `max_conversations` y descarta la que lleva más tiempo sin usarse, para
    que un proceso de larga vida no crezca sin límite.
    """
    def __init__(self, max_conversations: int = 200):
        self._conversations: OrderedDict[str, Conversation] = OrderedDict()
        self._max = max_conversations

    async def create(self) -> Conversation:
        conversation = Conversation(
            id=str(new_id()), started_at=describe_moment(datetime.now().astimezone())
        )
        self._conversations[conversation.id] = conversation
        while len(self._conversations) > self._max:
            self._conversations.popitem(last=False)
        return conversation

    async def get(self, conversation_id: str) -> Conversation | None:
        conversation = self._conversations.get(conversation_id)
        if conversation:
            self._conversations.move_to_end(conversation_id)
        return conversation
