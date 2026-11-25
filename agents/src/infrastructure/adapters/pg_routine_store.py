"""Rutinas del asistente y cada una de sus ejecuciones, en Postgres."""

from datetime import datetime, timezone
from typing import Literal, cast

from mindos_common.ids import new_id
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from agents.src.application.ports.routine_store import (
    Routine,
    RoutineAuthor,
    RoutineRun,
    RoutineRunStatus,
    RoutineStatusName,
    RoutineStorePort,
)
from agents.src.infrastructure.database.models import DbRoutine, DbRoutineRun
from agents.src.infrastructure.database.session import SessionFactory


def _as_utc(moment: datetime) -> datetime:
    # Sin zona se lee como UTC: el mismo criterio que el almacén en memoria,
    # para que «ya venció» no dependa del reloj local del proceso.
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _as_utc_optional(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return _as_utc(moment)


def _to_routine(row: DbRoutine) -> Routine:
    return Routine(
        id=row.id,
        title=row.title,
        prompt=row.prompt,
        schedule=row.schedule,
        schedule_description=row.schedule_description,
        timezone=row.timezone,
        status=cast(RoutineStatusName, row.status),
        created_by=cast(RoutineAuthor, row.created_by),
        created_at=_as_utc(row.created_at),
        next_run_at=_as_utc_optional(row.next_run_at),
        last_run_at=_as_utc_optional(row.last_run_at),
        runs_count=row.runs_count,
    )


def _to_run(row: DbRoutineRun) -> RoutineRun:
    return RoutineRun(
        id=row.id,
        routine_id=row.routine_id,
        started_at=_as_utc(row.started_at),
        finished_at=_as_utc_optional(row.finished_at),
        status=cast(RoutineRunStatus, row.status),
        output=row.output or "",
    )


class PgRoutineStore(RoutineStorePort):
    """
    Persistencia de rutinas en `agent_routines` y `agent_routine_runs`.

    Cada operación abre una sesión corta y confirma al terminar: el planificador
    llama al almacén fuera de una petición HTTP.
    """

    def __init__(self, session_factory: SessionFactory) -> None:
        self._sessions = session_factory

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
        row = DbRoutine(
            id=str(new_id()),
            title=title,
            prompt=prompt,
            schedule=schedule,
            schedule_description=schedule_description,
            timezone=timezone_name,
            status=status,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            next_run_at=_as_utc_optional(next_run_at),
            last_run_at=None,
            runs_count=0,
        )
        async with self._sessions() as session:
            session.add(row)
            await session.commit()
            return _to_routine(row)

    async def get(self, routine_id: str) -> Routine | None:
        async with self._sessions() as session:
            row = await session.get(DbRoutine, routine_id)
            if row is None:
                return None
            return _to_routine(row)

    async def list_routines(self) -> list[Routine]:
        stmt = (
            select(DbRoutine)
            .where(DbRoutine.status != "archived")
            # Misma hora de alta: se conserva el orden en que se crearon,
            # como hace el almacén en memoria.
            .order_by(DbRoutine.created_at.desc(), DbRoutine.id.asc())
        )
        async with self._sessions() as session:
            result = await session.execute(stmt)
            return [_to_routine(row) for row in result.scalars().all()]

    async def set_status(self, routine_id: str, status: RoutineStatusName) -> Routine | None:
        async with self._sessions() as session:
            row = await session.get(DbRoutine, routine_id)
            if row is None:
                return None
            row.status = status
            await session.commit()
            return _to_routine(row)

    async def start_run(self, routine_id: str, started_at: datetime) -> RoutineRun | None:
        # Se inserta directo. El índice único parcial rechaza la segunda fila
        # con status 'running' de la misma rutina, también si dos procesos
        # insertan a la vez. Mirar antes y luego insertar no alcanza.
        run = RoutineRun(
            id=str(new_id()),
            routine_id=routine_id,
            started_at=_as_utc(started_at),
            status="running",
        )
        stmt = insert(DbRoutineRun).values(
            id=run.id,
            routine_id=run.routine_id,
            started_at=run.started_at,
            status=run.status,
            output="",
        )
        async with self._sessions() as session:
            try:
                await session.execute(stmt)
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return None
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
        finished = _as_utc(finished_at)
        following = _as_utc_optional(next_run_at)
        async with self._sessions() as session:
            # El cierre y el contador van juntos: si una parte falla, no queda
            # la ejecución cerrada sin sumar la corrida, ni al revés.
            result = await session.execute(
                update(DbRoutineRun)
                .where(DbRoutineRun.id == run_id, DbRoutineRun.status == "running")
                .values(status=status, output=output, finished_at=finished)
                .returning(
                    DbRoutineRun.id,
                    DbRoutineRun.routine_id,
                    DbRoutineRun.started_at,
                    DbRoutineRun.finished_at,
                    DbRoutineRun.status,
                    DbRoutineRun.output,
                )
                .execution_options(synchronize_session=False)
            )
            row = result.one_or_none()
            if row is None:
                return None
            await session.execute(
                update(DbRoutine)
                .where(DbRoutine.id == row.routine_id)
                .values(
                    last_run_at=finished,
                    runs_count=DbRoutine.runs_count + 1,
                    next_run_at=following,
                )
                .execution_options(synchronize_session=False)
            )
            await session.commit()
            return _to_run(row)

    async def list_runs(self, routine_id: str) -> list[RoutineRun]:
        stmt = (
            select(DbRoutineRun)
            .where(DbRoutineRun.routine_id == routine_id)
            .order_by(DbRoutineRun.started_at.desc(), DbRoutineRun.id.desc())
        )
        async with self._sessions() as session:
            result = await session.execute(stmt)
            return [_to_run(row) for row in result.scalars().all()]

    async def list_due(self, at: datetime) -> list[Routine]:
        moment = _as_utc(at)
        # Una ejecución en curso saca a la rutina de la cola aunque su hora ya pasó.
        in_progress = (
            select(DbRoutineRun.id)
            .where(
                DbRoutineRun.routine_id == DbRoutine.id,
                DbRoutineRun.status == "running",
            )
            .correlate(DbRoutine)
            .exists()
        )
        stmt = (
            select(DbRoutine)
            .where(
                DbRoutine.status == "active",
                DbRoutine.next_run_at.is_not(None),
                DbRoutine.next_run_at <= moment,
                ~in_progress,
            )
            .order_by(DbRoutine.next_run_at.asc(), DbRoutine.id.asc())
        )
        async with self._sessions() as session:
            result = await session.execute(stmt)
            return [_to_routine(row) for row in result.scalars().all()]
