"""
DTOs de la Cognitive Query API (F2-T4): las 7 preguntas insignia de la visión de MindOS,
como endpoints de primera clase. "¿Cómo llegué a esta conclusión?" reutiliza
`ExplainNodeResponse` (F2-T3, ver `thinking_dto.py`) — no tiene DTO propio aquí.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from mindos_schemas.api.v1.thinking_dto import ExplainEvidenceDto


class PastThinkingItem(BaseModel):
    """Un nodo tal como era en el instante `at` consultado (F2-T4, "¿qué pensaba en fecha X?")."""
    node_id: UUID
    title: str
    content: str
    version: int
    object_type: str | None = None
    similarity: float
    as_of_created_at: datetime = Field(..., description="Fecha de creación de ESA versión específica")


class PastThinkingResponse(BaseModel):
    topic: str
    at: datetime
    items: list[PastThinkingItem] = Field(default_factory=list)


class SimilarIdeaItem(BaseModel):
    node_id: UUID
    title: str
    content: str
    object_type: str
    similarity: float
    created_at: datetime


class SimilarIdeasResponse(BaseModel):
    """F2-T4: "¿qué ideas similares tuve antes?" — KNN sobre object_type in (idea, hypothesis)."""
    node_id: UUID = Field(..., description="Nodo de referencia consultado")
    items: list[SimilarIdeaItem] = Field(default_factory=list)


class DecisionItem(BaseModel):
    node_id: UUID
    title: str
    content: str
    rationale: str | None = Field(default=None, description="Por qué se tomó (metadata.rationale)")
    created_at: datetime
    evidence_node_ids: list[UUID] = Field(default_factory=list, description="Nodos que evidencian la decisión")
    decides_node_ids: list[UUID] = Field(default_factory=list, description="Nodos afectados por la decisión")


class DecisionsResponse(BaseModel):
    """F2-T4: "¿qué decisiones tomé y por qué?"."""
    topic: str
    decisions: list[DecisionItem] = Field(default_factory=list)


class SupportResponse(BaseModel):
    """F2-T4: "¿qué respalda esta recomendación?" — cadena SUPPORTS/EVIDENCES + provenance."""
    node_id: UUID
    title: str
    content: str
    object_type: str | None = None
    support: list[ExplainEvidenceDto] = Field(default_factory=list)


class ContradictionPair(BaseModel):
    node_a_id: UUID
    node_a_title: str
    node_b_id: UUID
    node_b_title: str
    rationale: str | None = Field(default=None, description="Motivo de la contradicción, si se registró")
    confidence: float | None = Field(default=None, description="Confianza de la detección, si se registró")


class ContradictionsResponse(BaseModel):
    """F2-T4: "¿qué contradicciones existen en mi conocimiento?" — aristas CONTRADICTS (F2-T5)."""
    topic: str
    contradictions: list[ContradictionPair] = Field(default_factory=list)


class PatternBucket(BaseModel):
    period: str = Field(..., description="Periodo agregado, formato 'YYYY-MM'")
    object_type: str
    count: int


class PatternsResponse(BaseModel):
    """F2-T4: "¿qué patrones aparecen en mi forma de pensar?" — v1: temas/tipos por periodo."""
    buckets: list[PatternBucket] = Field(default_factory=list)
    total_nodes: int
    most_common_type: str | None = None
