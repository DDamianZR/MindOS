from abc import ABC, abstractmethod

from agents.src.application.ports.personal_agent import Conversation


class ConversationStorePort(ABC):
    """Puerto de persistencia de las conversaciones del asistente personal (F7-T3)."""

    @abstractmethod
    async def create(self) -> Conversation:
        """Abre una conversación nueva con un ID `uuid7`."""

    @abstractmethod
    async def get(self, conversation_id: str) -> Conversation | None:
        """Devuelve la conversación, o None si no existe (o el servicio se reinició)."""
