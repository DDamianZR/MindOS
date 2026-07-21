"""
Cognitive Query API (F2-T4): las 7 preguntas insignia de la visión de MindOS.
"¿Cómo llegué a esta conclusión?" reutiliza `/thinking/explain/{node_id}` (F2-T3) — no
tiene ruta propia aquí.

Router separado de `main.py` por el mismo motivo que `thinking_router.py`. Se importa el
MÓDULO `main` (no nombres sueltos) para `embedding_provider`: es un objeto, no una función,
así que solo el acceso calificado (`memory_main.embedding_provider`) respeta los
monkeypatch de los tests (ver convención ya usada en el resto del servicio).
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from mindos_schemas.api.v1.cognitive_dto import (
    ContradictionsResponse,
    DecisionsResponse,
    PastThinkingResponse,
    PatternsResponse,
    SimilarIdeasResponse,
    SupportResponse,
)

from memory.src import main as memory_main
from memory.src.application.services.cognitive_queries import CognitiveQueryService
from memory.src.main import get_repositories

router = APIRouter(prefix="/api/v1/cognitive", tags=["cognitive"])


def _service(repos) -> CognitiveQueryService:
    db_repo, vector_repo = repos
    return CognitiveQueryService(db_repo, vector_repo, memory_main.embedding_provider)


@router.get("/past-thinking", response_model=PastThinkingResponse)
async def past_thinking(
    topic: str,
    at: datetime,
    limit: int = 5,
    repos=Depends(get_repositories),
):
    """¿Qué pensaba en la fecha `at` sobre `topic`?"""
    return await _service(repos).past_thinking(topic, at, limit=limit)


@router.get("/similar", response_model=SimilarIdeasResponse)
async def similar(
    node_id: UUID,
    limit: int = 5,
    repos=Depends(get_repositories),
):
    """¿Qué ideas similares tuve antes?"""
    result = await _service(repos).similar(node_id, limit=limit)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Nodo {node_id} no encontrado.")
    return result


@router.get("/decisions", response_model=DecisionsResponse)
async def decisions(
    topic: str,
    limit: int = 5,
    repos=Depends(get_repositories),
):
    """¿Qué decisiones tomé y por qué?"""
    return await _service(repos).decisions(topic, limit=limit)


@router.get("/support", response_model=SupportResponse)
async def support(
    node_id: UUID,
    max_depth: int = 3,
    repos=Depends(get_repositories),
):
    """¿Qué respalda esta recomendación?"""
    result = await _service(repos).support(node_id, max_depth=max_depth)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Nodo {node_id} no encontrado.")
    return result


@router.get("/contradictions", response_model=ContradictionsResponse)
async def contradictions(
    topic: str,
    limit: int = 10,
    repos=Depends(get_repositories),
):
    """¿Qué contradicciones existen en mi conocimiento?"""
    return await _service(repos).contradictions(topic, limit=limit)


@router.get("/patterns", response_model=PatternsResponse)
async def patterns(
    limit: int = 500,
    repos=Depends(get_repositories),
):
    """¿Qué patrones aparecen en mi forma de pensar?"""
    return await _service(repos).patterns(limit=limit)
