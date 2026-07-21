from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IngestKnowledgeRequest(BaseModel):
    """
    DTO para crear o actualizar un nodo de conocimiento (Ingesta)
    """
    node_id: UUID | None = Field(
        default=None,
        description="ID del nodo si es una actualización. Si es nulo, se creará un nuevo nodo con UUIDv7."
    )
    entity_type: str = Field(
        ...,
        description="Tipo de entidad (concept, person, project, document, technology, event)"
    )
    title: str = Field(..., description="Título representativo de la información")
    content: str = Field(..., description="Cuerpo textual o contenido de la nota")
    author: str = Field(..., description="Creador o modificador de la información (usuario o ID del agente)")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos estructurados asociados al conocimiento"
    )


class IngestKnowledgeResponse(BaseModel):
    """
    DTO de respuesta para la ingesta de conocimiento exitosa
    """
    node_id: UUID = Field(..., description="ID final (UUIDv7) asignado al nodo de conocimiento")
    version: int = Field(..., description="Número de versión asignado")
    title: str = Field(..., description="Título de la entidad guardada")
    author: str = Field(..., description="Autor asignado al cambio")
    created_at: datetime = Field(..., description="Timestamp de creación/edición")


class SearchResultItem(BaseModel):
    """
    Elemento individual de respuesta en búsquedas
    """
    node_id: UUID = Field(..., description="ID del nodo de conocimiento")
    version: int = Field(..., description="Versión activa en el resultado")
    title: str = Field(..., description="Título de la nota")
    content: str = Field(..., description="Cuerpo textual de la nota")
    score: float = Field(..., description="Score de similitud vectorial o relevancia del RAG")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadatos asociados")


class SearchKnowledgeResponse(BaseModel):
    """
    Respuesta para búsquedas semánticas o híbridas
    """
    query: str = Field(..., description="Consulta original ejecutada")
    results: list[SearchResultItem] = Field(..., description="Lista ordenada de resultados de búsqueda")


class NodeVersionDto(BaseModel):
    """
    Representación de una versión histórica de un nodo
    """
    version: int = Field(..., description="Número de versión")
    title: str = Field(..., description="Título en esta versión")
    content: str = Field(..., description="Contenido en esta versión")
    author: str = Field(..., description="Autor que realizó la versión")
    created_at: datetime = Field(..., description="Fecha de creación de la versión")
    parent_version_id: UUID | None = Field(default=None, description="Versión de procedencia")


class GetNodeHistoryResponse(BaseModel):
    """
    Respuesta del historial de versiones de un nodo
    """
    node_id: UUID = Field(..., description="ID del nodo de conocimiento")
    entity_type: str = Field(..., description="Tipo de entidad")
    versions: list[NodeVersionDto] = Field(..., description="Lista cronológica de versiones")
