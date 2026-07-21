from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

StepKind = Literal["plan", "execute", "review", "replan"]
EpisodeStatus = Literal["running", "completed", "failed", "pending_approval"]


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
    kind: StepKind = Field(..., description="Tipo de paso del ciclo Planner→Executor→Reviewer")
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
    status: Literal["completed", "failed", "pending_approval"] = Field(..., description="Estado final del episodio")
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
