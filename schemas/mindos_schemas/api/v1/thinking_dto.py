from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from mindos_schemas.api.v1.memory_dto import SourceDto

StepKind = Literal["plan", "execute", "review", "replan", "conclude"]
EpisodeStatus = Literal["running", "completed", "failed", "pending_approval", "rejected"]


class CreateEpisodeRequest(BaseModel):
    """DTO para iniciar un episodio de razonamiento (F2-T1/F2-T2)."""
    episode_id: UUID = Field(..., description="ID del episodio (por convención, el correlation_id de la ejecución)")
    goal: str = Field(..., description="Meta u objetivo del agente en este episodio")
    correlation_id: UUID = Field(..., description="ID de correlación para trazabilidad distribuida")
    agent: str = Field(..., description="Nombre del servicio/agente que ejecuta (ej: 'AgentsService')")


class AppendStepRequest(BaseModel):
    """DTO para añadir un paso a un episodio existente."""
    step_id: UUID = Field(..., description="ID único del paso (UUIDv7)")
    step_index: int = Field(..., description="Orden del paso dentro del episodio")
    kind: StepKind = Field(
        ..., description="Tipo de paso: ciclo Planner→Executor→Reviewer, o 'conclude' (nodo de conocimiento creado)"
    )
    input: str | None = Field(default=None, description="Entrada del paso (prompt, tarea, etc.)")
    output: str | None = Field(default=None, description="Salida cruda del paso")
    capability_name: str | None = Field(default=None, description="Capacidad usada, si aplica (paso execute)")
    approved: bool | None = Field(default=None, description="Resultado de la revisión, si aplica (paso review)")
    feedback: str | None = Field(default=None, description="Retroalimentación de la revisión, si la hubo")
    knowledge_refs: list[UUID] = Field(
        default_factory=list, description="Nodos del Knowledge Graph citados o creados en este paso"
    )


class CloseEpisodeRequest(BaseModel):
    """DTO para cerrar un episodio."""
    status: EpisodeStatus = Field(..., description="Estado final del episodio")
    final_output: str | None = Field(default=None, description="Resultado final consolidado del episodio")


class ReasoningStepDto(BaseModel):
    """Representación de un paso persistido del Thinking Graph."""
    id: UUID
    episode_id: UUID
    step_index: int
    kind: str
    input: str | None = None
    output: str | None = None
    capability_name: str | None = None
    approved: bool | None = None
    feedback: str | None = None
    created_at: datetime
    knowledge_refs: list[UUID] = Field(default_factory=list)


class ReasoningEpisodeDto(BaseModel):
    """Representación completa de un episodio de razonamiento persistido, con sus pasos."""
    id: UUID
    goal: str
    correlation_id: UUID
    agent: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    final_output: str | None = None
    steps: list[ReasoningStepDto] = Field(default_factory=list)


class GetEpisodesByNodeResponse(BaseModel):
    """Respuesta de `/thinking/episodes/by-node/{node_id}` (F2-T1): episodios que citaron el nodo."""
    node_id: UUID
    episodes: list[ReasoningEpisodeDto]


class ExplainEvidenceDto(BaseModel):
    """
    Un nodo de evidencia/soporte en el árbol de explicación (F2-T3): "¿qué llevó a esto?".
    `relation_type` indica CÓMO se conecta con el nodo padre (DECIDES, EVIDENCES, DERIVED_FROM,
    ANSWERS). `supporting` anida recursivamente la evidencia DE la evidencia.
    """
    node_id: UUID
    title: str
    content: str
    object_type: str | None = None
    relation_type: str
    confidence: float = 0.5
    importance: float = 0.5
    source: SourceDto | None = Field(default=None, description="Fuente de origen (provenance), si la hay")
    supporting: list["ExplainEvidenceDto"] = Field(default_factory=list)


class ExplainNodeResponse(BaseModel):
    """
    Respuesta de `GET /thinking/explain/{node_id}` (F2-T3): "¿cómo llegué a esto?".
    Recorre hacia atrás las aristas DECIDES/EVIDENCES/DERIVED_FROM/ANSWERS que sustentan el
    nodo, y los episodios de razonamiento que lo produjeron o lo citaron.
    """
    node_id: UUID
    title: str
    content: str
    object_type: str | None = None
    supporting_evidence: list[ExplainEvidenceDto] = Field(default_factory=list)
    episodes: list[ReasoningEpisodeDto] = Field(default_factory=list)


class ExplainEpisodeResponse(BaseModel):
    """Respuesta de `GET /thinking/explain/episode/{episode_id}` (F2-T3): narra el episodio paso a paso."""
    episode: ReasoningEpisodeDto
    narrative: list[str] = Field(default_factory=list, description="Líneas de texto narrando cada paso en orden")
