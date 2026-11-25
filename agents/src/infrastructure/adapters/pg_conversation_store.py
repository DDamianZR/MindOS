"""Conversaciones del asistente en Postgres."""

import copy
from datetime import datetime, timezone

from mindos_common.ids import new_id
from sqlalchemy.dialects.postgresql import insert

from agents.src.application.ports.conversation_store import ConversationStorePort
from agents.src.application.ports.personal_agent import Conversation
from agents.src.infrastructure.adapters.in_memory_conversation_store import describe_moment
from agents.src.infrastructure.adapters.provider_serialization import to_jsonable
from agents.src.infrastructure.database.models import DbConversation
from agents.src.infrastructure.database.session import SessionFactory


class PgConversationStore(ConversationStorePort):
    """Persistencia de conversaciones sobre `agent_conversations`. Sobrevive a un reinicio."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._sessions = session_factory

    async def create(self) -> Conversation:
        now = datetime.now(timezone.utc)
        conversation = Conversation(
            id=str(new_id()),
            started_at=describe_moment(datetime.now().astimezone()),
        )
        async with self._sessions() as session:
            session.add(
                DbConversation(
                    id=conversation.id,
                    started_at_label=conversation.started_at,
                    messages=[],
                    transcript=[],
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
        return conversation

    async def get(self, conversation_id: str) -> Conversation | None:
        async with self._sessions() as session:
            row = await session.get(DbConversation, conversation_id)
            if row is None:
                return None
            # Se copia dentro de la sesión: al cerrarla, la fila queda desconectada.
            return Conversation(
                id=row.id,
                started_at=row.started_at_label,
                messages=copy.deepcopy(row.messages),
                transcript=copy.deepcopy(row.transcript),
            )

    async def save(self, conversation: Conversation) -> None:
        # Copia serializada: la conversación en memoria sigue con los objetos del SDK,
        # que el siguiente turno del mismo proceso reenvía tal cual.
        now = datetime.now(timezone.utc)
        messages = to_jsonable(conversation.messages)
        transcript = to_jsonable(conversation.transcript)
        stmt = insert(DbConversation).values(
            id=conversation.id,
            started_at_label=conversation.started_at,
            messages=messages,
            transcript=transcript,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[DbConversation.id],
            set_={
                "messages": stmt.excluded.messages,
                "transcript": stmt.excluded.transcript,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        async with self._sessions() as session:
            await session.execute(stmt)
            await session.commit()
