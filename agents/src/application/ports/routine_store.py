from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

RoutineStatusName = Literal["pending_activation", "active", "paused", "archived"]
RoutineRunStatus = Literal["running", "ok", "error"]
RoutineAuthor = Literal["assistant", "user"]


@dataclass
class Routine:
    """Tarea recurrente del asistente. No se borra: pasa a `archived`."""

    id: str
    title: str
    prompt: str
    schedule: str
    schedule_description: str
    timezone: str
    status: RoutineStatusName
    created_by: RoutineAuthor
    created_at: datetime
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    runs_count: int = 0


@dataclass
class RoutineRun:
    id: str
    routine_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: RoutineRunStatus = "running"
    output: str = ""


class RoutineStorePort(ABC):
    """Persistencia de rutinas programadas y de cada ejecución."""

    @abstractmethod
    async def create(
        self,
        *,
        title: str,
        prompt: str,
        schedule: str,
        schedule_description: str,
        timezone_name: str,
        status: RoutineStatusName,
        created_by: RoutineAuthor,
        next_run_at: datetime | None,
    ) -> Routine:
        """Guarda una rutina nueva con un ID `uuid7`."""

    @abstractmethod
    async def get(self, routine_id: str) -> Routine | None:
        """Devuelve la rutina, archivada o no, o None si no existe."""

    @abstractmethod
    async def list_routines(self) -> list[Routine]:
        """Todas menos las archivadas, las más recientes primero."""

    @abstractmethod
    async def set_status(self, routine_id: str, status: RoutineStatusName) -> Routine | None:
        """Cambia el estado. None si la rutina no existe."""

    @abstractmethod
    async def start_run(self, routine_id: str, started_at: datetime) -> RoutineRun | None:
        """
        Abre una ejecución en curso. None si la rutina no existe o ya tiene una ejecución
        sin terminar: nunca hay dos a la vez.
        """

    @abstractmethod
    async def finish_run(
        self,
        run_id: str,
        *,
        status: Literal["ok", "error"],
        output: str,
        finished_at: datetime,
        next_run_at: datetime | None,
    ) -> RoutineRun | None:
        """
        Cierra la ejecución, suma una corrida y deja la siguiente hora. No cambia el estado
        de la rutina: un fallo no la apaga. None si la ejecución no existe o ya estaba cerrada.
        """

    @abstractmethod
    async def list_runs(self, routine_id: str) -> list[RoutineRun]:
        """Ejecuciones de una rutina, las más recientes primero."""

    @abstractmethod
    async def list_due(self, at: datetime) -> list[Routine]:
        """
        Rutinas activas cuya hora ya llegó (`next_run_at <= at`) y no tienen una ejecución
        en curso. Las pendientes de activar no entran, aunque su hora haya pasado.
        """
