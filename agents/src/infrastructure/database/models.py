"""
Tablas del servicio de agentes (Fase 9): conversaciones del asistente, rutinas, sus ejecuciones
y el uso por turno. Viven en la misma base de Postgres que Memory pero con prefijo `agent_` y su
propia cadena de migraciones (`agents/alembic`, tabla de versión `alembic_version_agents`), para
que cada servicio evolucione su esquema sin pisar al otro.
"""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class DbConversation(Base):
    """
    Una conversación con el asistente. `messages` es el historial EN EL FORMATO DEL PROVEEDOR
    (lo que se reenvía a la API de Claude en cada turno), incluidos los bloques de razonamiento
    con su firma: se guarda tal cual, porque el proveedor rechaza o descarta razonamiento cuyo
    historial previo cambió. `transcript` es la versión para pintar en la interfaz.
    """
    __tablename__ = "agent_conversations"

    id = Column(String(36), primary_key=True)
    started_at_label = Column(Text, nullable=False)
    messages = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    transcript = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DbRoutine(Base):
    """Rutina programada. Nunca se borra: pasa a `status='archived'`."""
    __tablename__ = "agent_routines"

    id = Column(String(36), primary_key=True)
    title = Column(String(120), nullable=False)
    prompt = Column(Text, nullable=False)
    schedule = Column(String(100), nullable=False)
    schedule_description = Column(Text, nullable=False)
    timezone = Column(String(64), nullable=False)
    status = Column(String(30), nullable=False)  # pending_activation|active|paused|archived
    created_by = Column(String(20), nullable=False)  # assistant|user
    created_at = Column(DateTime(timezone=True), nullable=False)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    runs_count = Column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (
        # El planificador pregunta cada tic por las activas vencidas.
        Index("ix_agent_routines_status_next_run", "status", "next_run_at"),
    )


class DbRoutineRun(Base):
    __tablename__ = "agent_routine_runs"

    id = Column(String(36), primary_key=True)
    routine_id = Column(String(36), ForeignKey("agent_routines.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False)  # running|ok|error
    output = Column(Text, nullable=False, server_default=text("''"))

    __table_args__ = (
        Index("ix_agent_routine_runs_routine_started", "routine_id", "started_at"),
        # Nunca dos ejecuciones a la vez de la misma rutina, garantizado por la base: un segundo
        # INSERT con status='running' para la misma rutina falla aunque haya dos procesos.
        Index(
            "uq_agent_routine_runs_one_running", "routine_id", unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )


class DbUsageTurn(Base):
    """Un turno cerrado del asistente, con sus tokens. Base de `/assistant/stats`."""
    __tablename__ = "agent_usage_turns"

    id = Column(String(36), primary_key=True)
    # Sin clave foránea: el turno se registra aunque la conversación viva solo en memoria.
    conversation_id = Column(String(36), nullable=False)
    at = Column(DateTime(timezone=True), nullable=False)
    ok = Column(Boolean, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    tools = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # lista de nombres
    input_tokens = Column(Integer, nullable=False, server_default=text("0"))
    output_tokens = Column(Integer, nullable=False, server_default=text("0"))
    cache_read_input_tokens = Column(Integer, nullable=False, server_default=text("0"))
    cache_creation_input_tokens = Column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (Index("ix_agent_usage_turns_at", "at"),)
