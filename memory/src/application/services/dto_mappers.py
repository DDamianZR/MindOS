"""Funciones puras para mapear dicts de dominio (ThinkingGraphPort) a DTOs de schemas."""
from mindos_schemas.api.v1.thinking_dto import ReasoningEpisodeDto, ReasoningStepDto


def episode_dict_to_dto(ep: dict) -> ReasoningEpisodeDto:
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
