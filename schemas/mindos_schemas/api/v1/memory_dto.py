from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from mindos_schemas.domain import ObjectStatus, ObjectType, SourceKind


class SourceInput(BaseModel):
    """
    Origen de una captura (provenance, F1-T2), provisto opcionalmente en la ingesta.
    Si `uri` coincide con una fuente ya registrada del mismo `kind`, se reutiliza en vez
    de crear una fuente duplicada (p.ej. reprocesar el mismo PDF o mensaje de WhatsApp).
    """
    kind: SourceKind = Field(..., description="Tipo de origen (whatsapp, pdf, image, audio, web, cli, api, agent)")
    uri: str | None = Field(default=None, description="Identificador/ubicación estable del origen")
    raw_ref: str | None = Field(default=None, description="Referencia al artefacto crudo (id de mensaje, ruta...)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadatos crudos específicos del canal")


class SourceDto(BaseModel):
    """Representación de una fuente de origen ya persistida."""
    id: UUID = Field(..., description="ID de la fuente")
    kind: SourceKind = Field(..., description="Tipo de origen")
    uri: str | None = Field(default=None, description="Identificador/ubicación estable del origen")
    raw_ref: str | None = Field(default=None, description="Referencia al artefacto crudo")
    captured_at: datetime = Field(..., description="Fecha de captura de esta fuente")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadatos crudos del canal")


class EvidenceItem(BaseModel):
    """
    Una pieza de evidencia que respalda un Objeto Cognitivo (p.ej. una hipótesis o decisión).
    Al menos uno de `node_id`, `url` o `quote` debería estar presente para que la evidencia
    sea trazable (no se valida aquí de forma estricta para mantener el DTO simple).
    """
    node_id: UUID | None = Field(default=None, description="Nodo de conocimiento citado como evidencia")
    url: str | None = Field(default=None, description="URL externa citada como evidencia")
    quote: str | None = Field(default=None, description="Fragmento textual citado como evidencia")
    weight: float = Field(default=1.0, ge=0.0, description="Peso/relevancia relativa de esta evidencia")


class IngestKnowledgeRequest(BaseModel):
    """
    DTO para crear o actualizar un nodo de conocimiento (Ingesta)
    """
    node_id: UUID | None = Field(
        default=None,
        description="ID del nodo si es una actualización. Si es nulo, se creará un nuevo nodo con UUIDv7."
    )
    object_type: ObjectType = Field(
        ...,
        description="Tipo de Objeto Cognitivo (note, idea, hypothesis, decision, project, ...)"
    )
    title: str = Field(..., description="Título representativo de la información")
    content: str = Field(..., description="Cuerpo textual o contenido de la nota")
    author: str = Field(..., description="Creador o modificador de la información (usuario o ID del agente)")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos estructurados asociados al conocimiento"
    )
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Confianza en la veracidad/solidez de esta información (0-1)"
    )
    importance: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Importancia relativa de esta información para el usuario (0-1)"
    )
    status: ObjectStatus = Field(
        default=ObjectStatus.ACTIVE,
        description="Estado de ciclo de vida (draft, active, hypothesis, fact, superseded, archived)"
    )
    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Evidencias que respaldan esta información"
    )
    source: SourceInput | None = Field(
        default=None,
        description="Origen de esta captura (F1-T2). Los eventos de comunicación (Fase 3) siempre lo incluyen."
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
    object_type: ObjectType = Field(..., description="Tipo de Objeto Cognitivo persistido")
    confidence: float = Field(..., description="Confianza persistida (0-1)")
    importance: float = Field(..., description="Importancia persistida (0-1)")
    status: ObjectStatus = Field(..., description="Estado de ciclo de vida persistido")


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
    object_type: ObjectType | None = Field(default=None, description="Tipo de Objeto Cognitivo")
    confidence: float = Field(default=0.5, description="Confianza de la información (0-1)")
    importance: float = Field(default=0.5, description="Importancia de la información (0-1)")
    status: ObjectStatus = Field(default=ObjectStatus.ACTIVE, description="Estado de ciclo de vida")


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
    confidence: float = Field(default=0.5, description="Confianza de esta versión (0-1)")
    importance: float = Field(default=0.5, description="Importancia de esta versión (0-1)")
    status: ObjectStatus = Field(default=ObjectStatus.ACTIVE, description="Estado de ciclo de vida")
    evidence: list[EvidenceItem] = Field(default_factory=list, description="Evidencias asociadas")
    salience: float = Field(default=0.5, description="Relevancia dinámica recalculada (Fase 5)")
    tombstoned_at: datetime | None = Field(default=None, description="Fecha de archivado (soft-delete), si aplica")


class GetNodeHistoryResponse(BaseModel):
    """
    Respuesta del historial de versiones de un nodo
    """
    node_id: UUID = Field(..., description="ID del nodo de conocimiento")
    object_type: ObjectType = Field(..., description="Tipo de Objeto Cognitivo")
    versions: list[NodeVersionDto] = Field(..., description="Lista cronológica de versiones")


class VersionProvenanceDto(BaseModel):
    """La fuente de origen (si existe) de una versión específica del nodo."""
    version: int = Field(..., description="Número de versión")
    created_at: datetime = Field(..., description="Fecha de creación de la versión")
    author: str = Field(..., description="Autor de la versión")
    source: SourceDto | None = Field(default=None, description="Fuente de origen de esta versión, si la tiene")


class GetNodeProvenanceResponse(BaseModel):
    """
    Respuesta de trazabilidad de origen (F1-T2): la cadena de versiones del nodo junto con
    la fuente de la que provino cada una (whatsapp, pdf, cli, ...), cuando se conoce.
    """
    node_id: UUID = Field(..., description="ID del nodo de conocimiento")
    chain: list[VersionProvenanceDto] = Field(..., description="Cadena cronológica de versiones + su fuente")


class TimeTravelRelationDto(BaseModel):
    """Una relación vigente en el instante consultado (F1-T3)."""
    source_id: UUID = Field(..., description="Nodo de origen de la relación")
    target_id: UUID = Field(..., description="Nodo de destino de la relación")
    relation_type: str = Field(..., description="Tipo de relación")


class TimeTravelResponse(BaseModel):
    """
    Respuesta de la consulta temporal "as-of" (F1-T3): reconstruye el estado del nodo
    (versión vigente + relaciones vigentes) tal como era en el instante `at`, sin importar
    el estado actual (incluye versiones hoy archivadas, si en ese momento estaban activas).
    """
    node_id: UUID = Field(..., description="ID del nodo de conocimiento")
    at: datetime = Field(..., description="Instante consultado")
    found: bool = Field(..., description="Si existía alguna versión del nodo en ese instante")
    version: NodeVersionDto | None = Field(default=None, description="Versión vigente en `at`, si existía")
    relations: list[TimeTravelRelationDto] = Field(
        default_factory=list, description="Relaciones vigentes en `at`"
    )


class ArchiveNodeResponse(BaseModel):
    """
    Respuesta de archivar/restaurar un nodo (F1-T4, soft-delete). Nunca implica borrado físico:
    solo cambia si la versión vigente queda oculta por defecto de búsquedas y lecturas.
    """
    node_id: UUID = Field(..., description="ID del nodo de conocimiento")
    archived: bool = Field(..., description="Estado resultante: True si quedó archivado, False si activo")
