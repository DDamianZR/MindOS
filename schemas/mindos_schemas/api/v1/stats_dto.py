# DTOs API v1 — estadísticas de la memoria (Fase 8, portada del Dashboard)
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CountItem(BaseModel):
    """Un recuento por categoría (tipo de objeto, canal de origen, tipo de relación...)."""
    key: str
    count: int


class ActivityDay(BaseModel):
    """Actividad de un día: nodos creados (versión 1) y actualizados (versiones posteriores)."""
    date: date
    created: int
    updated: int


class RecentNode(BaseModel):
    node_id: UUID
    title: str
    object_type: str | None = None
    version: int
    created_at: datetime


class MemoryStatsResponse(BaseModel):
    """
    `GET /api/v1/memory/stats`: lo que hay en la memoria, para la portada del Dashboard.
    Solo cuenta lo vigente; lo archivado (soft-delete) va aparte en `archived_nodes`.
    """
    generated_at: datetime
    nodes: int = Field(..., description="Nodos con versión vigente no archivada")
    archived_nodes: int
    versions: int = Field(..., description="Total de versiones de todos los nodos")
    relations: int = Field(..., description="Relaciones activas del Knowledge Graph")
    sources: int = Field(..., description="Fuentes de origen registradas (provenance)")
    contradictions: int = Field(..., description="Relaciones CONTRADICTS activas")
    by_type: list[CountItem] = Field(default_factory=list, description="Nodos por object_type, de mayor a menor")
    by_source: list[CountItem] = Field(default_factory=list, description="Fuentes por kind, de mayor a menor")
    by_relation: list[CountItem] = Field(default_factory=list, description="Relaciones por tipo, de mayor a menor")
    activity: list[ActivityDay] = Field(
        default_factory=list,
        description="Últimos 30 días incluido hoy (UTC), uno por día aunque sea cero, ascendente",
    )
    recent_thinking: list[RecentNode] = Field(
        default_factory=list,
        description="Últimos 8 nodos de tipo decision/insight/learning/hypothesis, del más reciente al más antiguo",
    )
