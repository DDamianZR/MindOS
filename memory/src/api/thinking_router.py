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
    GetEpisodesByNodeResponse,
    ReasoningEpisodeDto,
    ReasoningStepDto,
)

from memory.src.config import settings
from memory.src.main import get_thinking_graph_repo

router = APIRouter(prefix="/api/v1/thinking", tags=["thinking"])


def _episode_dict_to_dto(ep: dict) -> ReasoningEpisodeDto:
    return ReasoningEpisodeDto(
        id=ep["id"], goal=ep["goal"], correlation_id=ep["correlation_id"], agent=ep["agent"],
        status=ep["status"], started_at=ep["started_at"], ended_at=ep["ended_at"],
        final_output=ep["final_output"],
        steps=[
            ReasoningStepDto(
                id=s["id"], episode_id=s["episode_id"], step_index=s["step_index"], kind=s["kind"],
                input=s["input"], output=s["output"], capability_name=s["capability_name"],
                approved=s["approved"], feedback=s["feedback"], created_at=s["created_at"],
                knowledge_refs=s["knowledge_refs"],
            ) for s in ep.get("steps", [])
        ],
    )


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
    return _episode_dict_to_dto(episode)


@router.get("/episodes/by-node/{node_id}", response_model=GetEpisodesByNodeResponse)
async def get_episodes_by_node(
    node_id: UUID,
    thinking_repo=Depends(get_thinking_graph_repo),
):
    episodes = await thinking_repo.get_episodes_by_node(node_id)
    return GetEpisodesByNodeResponse(
        node_id=node_id, episodes=[_episode_dict_to_dto(ep) for ep in episodes]
    )
