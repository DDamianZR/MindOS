"""
Rutinas programadas (Fase 8). Las que crea la persona desde aquí nacen activas; las que
propone el asistente nacen pendientes y solo corren después de activarlas.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from mindos_schemas.api.v1.routine_dto import (
    CreateRoutineRequest,
    RoutineDto,
    RoutineListResponse,
    RoutineRunDto,
    RoutineRunsResponse,
)

from agents.src import main as agents_main
from agents.src.application.assistant.routines import RoutineRunner, ScheduleError, register_routine
from agents.src.application.ports.routine_store import Routine, RoutineRun, RoutineStatusName
from agents.src.config import settings

router = APIRouter(prefix="/api/v1/agents/routines", tags=["routines"])


def _routine_dto(routine: Routine) -> RoutineDto:
    return RoutineDto.model_validate(routine, from_attributes=True)


def _run_dto(run: RoutineRun) -> RoutineRunDto:
    return RoutineRunDto.model_validate(run, from_attributes=True)


async def _get_or_404(routine_id: str) -> Routine:
    routine = await agents_main.get_routine_store().get(routine_id)
    if routine is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontramos esa rutina.")
    return routine


def _runner() -> RoutineRunner:
    return RoutineRunner(
        agents_main.get_routine_store(),
        agents_main.get_conversation_store(),
        agents_main.get_personal_agent(agents_main.get_assistant_http_client()),
    )


async def _run_in_background(routine_id: str) -> None:
    await _runner().run(routine_id, allow_paused=True)


@router.get("", response_model=RoutineListResponse)
async def list_routines():
    routines = await agents_main.get_routine_store().list_routines()
    return RoutineListResponse(routines=[_routine_dto(routine) for routine in routines])


@router.post("", response_model=RoutineDto, status_code=status.HTTP_201_CREATED)
async def create_routine(body: CreateRoutineRequest):
    try:
        routine = await register_routine(
            agents_main.get_routine_store(),
            title=body.title,
            prompt=body.prompt,
            schedule=body.schedule,
            timezone_name=body.timezone,
            configured_timezone=settings.ROUTINES_TIMEZONE,
            status="active",
            created_by="user",
        )
    except ScheduleError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _routine_dto(routine)


@router.post("/{routine_id}/activate", response_model=RoutineDto)
async def activate_routine(routine_id: str):
    return await _set_status(routine_id, "active")


@router.post("/{routine_id}/pause", response_model=RoutineDto)
async def pause_routine(routine_id: str):
    return await _set_status(routine_id, "paused")


@router.post("/{routine_id}/archive", response_model=RoutineDto)
async def archive_routine(routine_id: str):
    return await _set_status(routine_id, "archived")


@router.post("/{routine_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_routine_now(routine_id: str, background: BackgroundTasks):
    routine = await _get_or_404(routine_id)
    if routine.status == "archived":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta rutina está archivada.")
    if routine.status == "pending_activation":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Activa la rutina para que pueda ejecutarse.",
        )
    runs = await agents_main.get_routine_store().list_runs(routine_id)
    if any(run.status == "running" for run in runs):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta rutina ya se está ejecutando.",
        )
    background.add_task(_run_in_background, routine_id)
    return {"detail": "La rutina se está ejecutando.", "routine_id": routine_id}


@router.get("/{routine_id}/runs", response_model=RoutineRunsResponse)
async def list_routine_runs(routine_id: str):
    await _get_or_404(routine_id)
    runs = await agents_main.get_routine_store().list_runs(routine_id)
    return RoutineRunsResponse(runs=[_run_dto(run) for run in runs])


async def _set_status(routine_id: str, target: RoutineStatusName) -> RoutineDto:
    routine = await _get_or_404(routine_id)
    if routine.status == "archived" and target != "archived":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta rutina está archivada.")
    if target == "paused" and routine.status == "pending_activation":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Activa la rutina antes de pausarla.",
        )
    if routine.status != target:
        updated = await agents_main.get_routine_store().set_status(routine_id, target)
        if updated is not None:
            routine = updated
    return _routine_dto(routine)
