from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class DbCognitiveObject(Base):
    """
    Representación relacional inmutable de un Objeto Cognitivo (knowledge_nodes).
    """
    __tablename__ = "knowledge_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True)
    entity_type = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    versions = relationship("DbObjectVersion", back_populates="node", cascade="all, delete-orphan")


class DbObjectVersion(Base):
    """
    Snapshot de la versión inmutable de un Objeto Cognitivo (knowledge_node_versions).
    Contiene el texto, los metadatos y el embedding vectorial (pgvector) de esta versión.
    """
    __tablename__ = "knowledge_node_versions"

    id = Column(UUID(as_uuid=True), primary_key=True)
    node_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(String, nullable=False)
    embedding = Column(Vector(384), nullable=True) # pgvector de 384 dimensiones
    metadata_json = Column("metadata", JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    author = Column(String(100), nullable=False)
    parent_version_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_node_versions.id"), nullable=True)

    node = relationship("DbCognitiveObject", back_populates="versions")

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
