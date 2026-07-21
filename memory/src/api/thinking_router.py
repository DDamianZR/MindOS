"""
Endpoints del Thinking Graph (F2-T1/F2-T2/F2-T3): CRUD de episodios de razonamiento y,
más abajo (F2-T3), explicabilidad.

Router separado de `main.py` (que ya supera las 600 líneas): importa las dependencias
compartidas (`get_thinking_graph_repo`, `settings`) directamente porque son FUNCIONES —
su cuerpo resuelve nombres en el namespace de `main.py`, así que un test que monkeypatchea
`memory_main.in_memory_thinking_graph` sigue funcionando sin importar desde dónde se llame.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from mindos_schemas.api.v1.thinking_dto import (
    AppendStepRequest,
    CloseEpisodeRequest,
    CreateEpisodeRequest,
    ExplainEpisodeResponse,
    ExplainNodeResponse,
    GetEpisodesByNodeResponse,
    ReasoningEpisodeDto,
)

from memory.src.application.services.dto_mappers import episode_dict_to_dto
from memory.src.application.services.explainability import ExplainabilityService
from memory.src.config import settings
from memory.src.main import get_repositories, get_thinking_graph_repo

router = APIRouter(prefix="/api/v1/thinking", tags=["thinking"])


@router.post("/episodes", status_code=status.HTTP_201_CREATED)
async def create_episode(
    request: CreateEpisodeRequest,
    thinking_repo=Depends(get_thinking_graph_repo),
):
    await thinking_repo.create_episode(
        episode_id=request.episode_id, goal=request.goal,
        correlation_id=request.correlation_id, agent=request.agent,
    )
    if settings.DATABASE_TYPE == "postgres":
        await thinking_repo.session.commit()
    return {"episode_id": request.episode_id, "status": "running"}


@router.post("/episodes/{episode_id}/steps", status_code=status.HTTP_201_CREATED)
async def append_step(
    episode_id: UUID,
    request: AppendStepRequest,
    thinking_repo=Depends(get_thinking_graph_repo),
):
    await thinking_repo.append_step(
        step_id=request.step_id, episode_id=episode_id, step_index=request.step_index,
        kind=request.kind, input_text=request.input, output_text=request.output,
        capability_name=request.capability_name, approved=request.approved,
        feedback=request.feedback, knowledge_refs=request.knowledge_refs,
    )
    if settings.DATABASE_TYPE == "postgres":
        await thinking_repo.session.commit()
    return {"episode_id": episode_id, "step_id": request.step_id}


@router.post("/episodes/{episode_id}/close")
async def close_episode(
    episode_id: UUID,
    request: CloseEpisodeRequest,
    thinking_repo=Depends(get_thinking_graph_repo),
):
    episode = await thinking_repo.get_episode(episode_id)
    if not episode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Episodio {episode_id} no encontrado.")

    await thinking_repo.close_episode(episode_id, status=request.status, final_output=request.final_output)
    if settings.DATABASE_TYPE == "postgres":
        await thinking_repo.session.commit()
    return {"episode_id": episode_id, "status": request.status}


@router.get("/episodes/{episode_id}", response_model=ReasoningEpisodeDto)
async def get_episode(
    episode_id: UUID,
    thinking_repo=Depends(get_thinking_graph_repo),
):
    episode = await thinking_repo.get_episode(episode_id)
    if not episode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Episodio {episode_id} no encontrado.")
    return episode_dict_to_dto(episode)


@router.get("/episodes/by-node/{node_id}", response_model=GetEpisodesByNodeResponse)
async def get_episodes_by_node(
    node_id: UUID,
    thinking_repo=Depends(get_thinking_graph_repo),
):
    episodes = await thinking_repo.get_episodes_by_node(node_id)
    return GetEpisodesByNodeResponse(
        node_id=node_id, episodes=[episode_dict_to_dto(ep) for ep in episodes]
    )


@router.get("/explain/episode/{episode_id}", response_model=ExplainEpisodeResponse)
async def explain_episode(
    episode_id: UUID,
    thinking_repo=Depends(get_thinking_graph_repo),
    repos=Depends(get_repositories),
):
    """F2-T3: narra un episodio de razonamiento paso a paso."""
    db_repo, _ = repos
    service = ExplainabilityService(db_repo, thinking_repo)
    result = await service.explain_episode(episode_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Episodio {episode_id} no encontrado.")
    return result


@router.get("/explain/{node_id}", response_model=ExplainNodeResponse)
async def explain_node(
    node_id: UUID,
    max_depth: int = 3,
    thinking_repo=Depends(get_thinking_graph_repo),
    repos=Depends(get_repositories),
):
    """
    F2-T3: "¿cómo llegué a esto?". Recorre hacia atrás las evidencias/decisiones/hipótesis
    que sustentan el nodo (DECIDES/EVIDENCES/DERIVED_FROM/ANSWERS) y los episodios de
    razonamiento que lo produjeron o citaron.
    """
    db_repo, _ = repos
    service = ExplainabilityService(db_repo, thinking_repo)
    result = await service.explain_node(node_id, max_depth=max_depth)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Nodo {node_id} no encontrado.")
    return result
