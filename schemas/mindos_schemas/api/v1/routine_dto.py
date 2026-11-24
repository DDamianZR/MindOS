# DTOs API v1 — rutinas del agente (Fase 8)
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RoutineStatus = Literal["pending_activation", "active", "paused", "archived"]


class RoutineDto(BaseModel):
    """
    Una tarea recurrente del agente: a la hora indicada ejecuta `prompt` como un turno del
    asistente y guarda el resultado. Las que crea el asistente nacen en `pending_activation`:
    solo corren cuando la persona las activa (human-in-the-loop). Nunca se borran: se archivan.
    """
    id: str
    title: str
    prompt: str = Field(..., description="Lo que el agente debe hacer en cada ejecución")
    schedule: str = Field(..., description="Expresión cron de 5 campos, p.ej. '0 9 * * 1' = lunes 9:00")
    schedule_description: str = Field(..., description="La expresión cron en español legible")
    timezone: str = Field(..., description="Zona horaria IANA en que se interpreta `schedule`")
    status: RoutineStatus
    created_by: Literal["assistant", "user"]
    created_at: datetime
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    runs_count: int = 0


class RoutineRunDto(BaseModel):
    id: str
    routine_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: Literal["running", "ok", "error"]
    output: str = Field("", description="Texto final que produjo el agente (o el error legible)")


class CreateRoutineRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    prompt: str = Field(..., min_length=1, max_length=4000)
    schedule: str = Field(..., description="Expresión cron de 5 campos")
    timezone: str | None = Field(default=None, description="IANA; nulo = la del servidor (ROUTINES_TIMEZONE)")


class RoutineListResponse(BaseModel):
    routines: list[RoutineDto]


class RoutineRunsResponse(BaseModel):
    runs: list[RoutineRunDto]
