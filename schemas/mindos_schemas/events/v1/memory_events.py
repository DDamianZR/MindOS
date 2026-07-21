from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeCreatedEventData(BaseModel):
    """
    Payload de datos para el evento com.mindos.memory.knowledge.created
    """
    node_id: UUID = Field(..., description="ID único (UUIDv7) del nodo de conocimiento")
    entity_type: str = Field(..., description="Tipo de entidad (concept, person, project, document, technology)")
    version: int = Field(default=1, description="Número de versión inicial (1)")
    title: str = Field(..., description="Título de la nota o entidad")
    author: str = Field(..., description="Identificador del autor (usuario o agente)")


class KnowledgeUpdatedEventData(BaseModel):
    """
    Payload de datos para el evento com.mindos.memory.knowledge.updated
    """
    node_id: UUID = Field(..., description="ID del nodo de conocimiento actualizado")
    version: int = Field(..., description="Nuevo número de versión generado")
    title: str = Field(..., description="Título de la nota o entidad en esta versión")
    author: str = Field(..., description="Identificador del autor que actualizó")
    parent_version_id: UUID | None = Field(default=None, description="ID de la versión de la cual desciende")


class RelationCreatedEventData(BaseModel):
    """
    Payload de datos para el evento com.mindos.memory.relation.created
    """
    source_id: UUID = Field(..., description="ID del nodo de origen")
    target_id: UUID = Field(..., description="ID del nodo de destino")
    relation_type: str = Field(..., description="Tipo de relación (ej: PART_OF, RELATED_TO)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadatos de la relación")


class RelationDeletedEventData(BaseModel):
    """
    Payload de datos para el evento com.mindos.memory.relation.deleted
    """
    source_id: UUID = Field(..., description="ID del nodo de origen")
    target_id: UUID = Field(..., description="ID del nodo de destino")
    relation_type: str = Field(..., description="Tipo de relación eliminada")
