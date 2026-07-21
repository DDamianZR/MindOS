from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

from memory.src.config import settings

Base = declarative_base()

class DbCognitiveObject(Base):
    """
    Representación relacional inmutable de un Objeto Cognitivo (knowledge_nodes).
    """
    __tablename__ = "knowledge_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True)
    object_type = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    versions = relationship("DbObjectVersion", back_populates="node", cascade="all, delete-orphan")


class DbSource(Base):
    """
    Fuente de origen de una captura (provenance) — F1-T2. Ej: un mensaje de WhatsApp, un PDF,
    una página web, la CLI o un agente. Permite responder "¿de dónde vino este conocimiento?".
    """
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True)
    kind = Column(String(30), nullable=False)  # whatsapp|pdf|image|audio|web|cli|api|agent
    uri = Column(String, nullable=True)
    raw_ref = Column(String, nullable=True)
    captured_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_json = Column("metadata", JSONB, default=dict, nullable=False)


class DbObjectVersion(Base):
    """
    Snapshot de la versión inmutable de un Objeto Cognitivo (knowledge_node_versions).
    Contiene el texto, los metadatos, el embedding vectorial (pgvector) y los atributos
    cognitivos ricos (confianza, importancia, estado, evidencia) de esta versión.
    """
    __tablename__ = "knowledge_node_versions"

    id = Column(UUID(as_uuid=True), primary_key=True)
    node_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(String, nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)  # = EMBEDDING_DIM (nomic-embed-text: 768)
    metadata_json = Column("metadata", JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    author = Column(String(100), nullable=False)
    parent_version_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_node_versions.id"), nullable=True)

    # --- Atributos cognitivos ricos (F1-T1) ---
    confidence = Column(Float, nullable=False, default=0.5)
    importance = Column(Float, nullable=False, default=0.5)
    status = Column(String(20), nullable=False, default="active")
    evidence = Column(JSONB, default=list, nullable=False)  # [{node_id|url|quote, weight}]
    salience = Column(Float, nullable=False, default=0.5)  # recalculado por el agente de consolidación (Fase 5)
    tombstoned_at = Column(DateTime(timezone=True), nullable=True)  # soft-delete (F1-T4); nunca se borra físico

    # --- Provenance (F1-T2) ---
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=True)

    node = relationship("DbCognitiveObject", back_populates="versions")
    source = relationship("DbSource")

    __table_args__ = (
        UniqueConstraint("node_id", "version", name="uidx_node_version"),
    )


class DbCognitiveRelation(Base):
    """
    Relación temporal activa en el Grafo de Conocimiento / Pensamiento (relations).
    """
    __tablename__ = "relations"

    source_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), primary_key=True)
    target_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), primary_key=True)
    relation_type = Column(String(50), primary_key=True)
    valid_from = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    valid_to = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column("metadata", JSONB, default=dict, nullable=False)


class DbEventLog(Base):
    """
    Registro histórico inmutable de comandos/eventos (knowledge_event_log).
    """
    __tablename__ = "knowledge_event_log"

    event_id = Column(UUID(as_uuid=True), primary_key=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSONB, default=dict, nullable=False)
    logged_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DbReasoningEpisode(Base):
    """
    Un episodio de razonamiento del ciclo Planner→Executor→Reviewer (Thinking Graph, F2-T1).
    Registra el PROCESO (cómo se llegó a algo), a diferencia de `knowledge_nodes` que registra
    el resultado (qué se sabe). El `id` coincide con el `correlation_id` de la ejecución.
    """
    __tablename__ = "reasoning_episodes"

    id = Column(UUID(as_uuid=True), primary_key=True)
    goal = Column(String, nullable=False)
    correlation_id = Column(UUID(as_uuid=True), nullable=False)
    agent = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="running")  # running|completed|failed|pending_approval
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    final_output = Column(String, nullable=True)

    steps = relationship(
        "DbReasoningStep", back_populates="episode",
        cascade="all, delete-orphan", order_by="DbReasoningStep.step_index",
    )


class DbReasoningStep(Base):
    """Un paso individual (plan|execute|review|replan) dentro de un `DbReasoningEpisode`."""
    __tablename__ = "reasoning_steps"

    id = Column(UUID(as_uuid=True), primary_key=True)
    episode_id = Column(
        UUID(as_uuid=True), ForeignKey("reasoning_episodes.id", ondelete="CASCADE"), nullable=False
    )
    step_index = Column(Integer, nullable=False)
    kind = Column(String(20), nullable=False)  # plan|execute|review|replan
    input = Column(String, nullable=True)
    output = Column(String, nullable=True)
    capability_name = Column(String(100), nullable=True)
    approved = Column(Boolean, nullable=True)  # None = no aplica (ej. paso de tipo 'plan')
    feedback = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    knowledge_refs = Column(JSONB, default=list, nullable=False)  # [node_id, ...] citados/creados

    episode = relationship("DbReasoningEpisode", back_populates="steps")
