from abc import ABC, abstractmethod

from agents.src.application.ports.personal_agent import Conversation


class ConversationStorePort(ABC):
    """Puerto de persistencia de las conversaciones del asistente personal (F7-T3)."""

    @abstractmethod
    async def create(self) -> Conversation:
        """Abre una conversación nueva con un ID `uuid7`."""

    @abstractmethod
    async def get(self, conversation_id: str) -> Conversation | None:
        """Devuelve la conversación, o None si no existe."""

    @abstractmethod
    async def save(self, conversation: Conversation) -> None:
        """
        Persiste el estado actual de la conversación (historial del proveedor y transcripción).
        Se llama al cerrar cada turno. El historial es solo-anexar: lo guardado debe poder
        reenviarse al proveedor tal cual, con los bloques de razonamiento y sus firmas intactos.
        """
