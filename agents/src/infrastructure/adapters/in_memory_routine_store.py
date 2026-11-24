from datetime import datetime, timezone
from typing import Literal

from mindos_common.ids import new_id

from agents.src.application.ports.routine_store import (
    Routine,
    RoutineAuthor,
    RoutineRun,
    RoutineStatusName,
    RoutineStorePort,
)


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


class InMemoryRoutineStore(RoutineStorePort):
    """
    Rutinas en memoria del proceso, con el mismo alcance que `InMemoryConversationStore`:
    alcanza para un Agents Service de un solo proceso y se pierde al reiniciar.
    """

    def __init__(self) -> None:
        self._routines: dict[str, Routine] = {}
        self._runs: dict[str, list[RoutineRun]] = {}
        self._runs_by_id: dict[str, RoutineRun] = {}
        self._running: set[str] = set()

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
        routine = Routine(
            id=str(new_id()),
            title=title,
            prompt=prompt,
            schedule=schedule,
            schedule_description=schedule_description,
            timezone=timezone_name,
            status=status,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            next_run_at=next_run_at,
        )
        self._routines[routine.id] = routine
        self._runs[routine.id] = []
        return routine

    async def get(self, routine_id: str) -> Routine | None:
        return self._routines.get(routine_id)

    async def list_routines(self) -> list[Routine]:
        visible = [routine for routine in self._routines.values() if routine.status != "archived"]
        visible.sort(key=lambda routine: routine.created_at, reverse=True)
        return visible

    async def set_status(self, routine_id: str, status: RoutineStatusName) -> Routine | None:
        routine = self._routines.get(routine_id)
        if routine is None:
            return None
        routine.status = status
        return routine

    async def start_run(self, routine_id: str, started_at: datetime) -> RoutineRun | None:
        if routine_id not in self._routines or routine_id in self._running:
            return None
        self._running.add(routine_id)
        run = RoutineRun(
            id=str(new_id()),
            routine_id=routine_id,
            started_at=started_at,
            status="running",
        )
        self._runs.setdefault(routine_id, []).append(run)
        self._runs_by_id[run.id] = run
        return run

    async def finish_run(
        self,
        run_id: str,
        *,
        status: Literal["ok", "error"],
        output: str,
        finished_at: datetime,
        next_run_at: datetime | None,
    ) -> RoutineRun | None:
        run = self._runs_by_id.get(run_id)
        if run is None or run.status != "running":
            return None
        run.status = status
        run.output = output
        run.finished_at = finished_at
        self._running.discard(run.routine_id)
        routine = self._routines.get(run.routine_id)
        if routine is not None:
            routine.last_run_at = finished_at
            routine.runs_count += 1
            routine.next_run_at = next_run_at
        return run

    async def list_runs(self, routine_id: str) -> list[RoutineRun]:
        return list(reversed(self._runs.get(routine_id, [])))

    async def list_due(self, at: datetime) -> list[Routine]:
        moment = _as_utc(at)
        due = [
            routine for routine in self._routines.values()
            if routine.status == "active"
            and routine.id not in self._running
            and routine.next_run_at is not None
            and _as_utc(routine.next_run_at) <= moment
        ]
        due.sort(key=_next_run_utc)
        return due


def _next_run_utc(routine: Routine) -> datetime:
    # list_due ya descartó las que no tienen hora.
    assert routine.next_run_at is not None
    return _as_utc(routine.next_run_at)
