"""Estadísticas de la memoria para la portada del Dashboard."""
from fastapi import APIRouter, Depends
from mindos_schemas.api.v1.stats_dto import MemoryStatsResponse

from memory.src.application.services.stats_service import StatsService
from memory.src.main import get_repositories

router = APIRouter(prefix="/api/v1/memory", tags=["stats"])


@router.get("/stats", response_model=MemoryStatsResponse)
async def memory_stats(repos=Depends(get_repositories)) -> MemoryStatsResponse:
    """Lo que hay en la memoria: recuentos, actividad de los últimos días y pensamiento reciente."""
    db_repo, _ = repos
    return await StatsService(db_repo).get_stats()
