import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from memory.src.application.ports.thinking_graph import ThinkingGraphPort
from memory.src.infrastructure.database.models import DbReasoningEpisode, DbReasoningStep


class PgThinkingGraphRepository(ThinkingGraphPort):
    """
    Implementación concreta de ThinkingGraphPort para PostgreSQL utilizando SQLAlchemy
    AsyncSession. Las búsquedas por `knowledge_refs` usan el operador de contención JSONB
    (`@>`), acelerado por el índice GIN `jsonb_path_ops` de la migración 0004.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_episode(self, episode_id: UUID, goal: str, correlation_id: UUID, agent: str) -> None:
        self.session.add(DbReasoningEpisode(
            id=episode_id, goal=goal, correlation_id=correlation_id, agent=agent, status="running",
        ))
        await self.session.flush()

    async def append_step(
        self,
        step_id: UUID,
        episode_id: UUID,
        step_index: int,
        kind: str,
        input_text: str | None,
        output_text: str | None,
        capability_name: str | None = None,
        approved: bool | None = None,
        feedback: str | None = None,
        knowledge_refs: list[UUID] | None = None,
    ) -> None:
        self.session.add(DbReasoningStep(
            id=step_id, episode_id=episode_id, step_index=step_index, kind=kind,
            input=input_text, output=output_text, capability_name=capability_name,
            approved=approved, feedback=feedback,
            knowledge_refs=[str(r) for r in (knowledge_refs or [])],
        ))
        await self.session.flush()

    async def close_episode(self, episode_id: UUID, status: str, final_output: str | None = None) -> None:
        stmt = select(DbReasoningEpisode).where(DbReasoningEpisode.id == episode_id)
        result = await self.session.execute(stmt)
        episode = result.scalar_one_or_none()
        if episode:
            episode.status = status
            episode.ended_at = datetime.now(timezone.utc)
            episode.final_output = final_output
            await self.session.flush()

    def _step_row_to_dict(self, s: DbReasoningStep) -> dict[str, Any]:
        return {
            "id": s.id, "episode_id": s.episode_id, "step_index": s.step_index, "kind": s.kind,
            "input": s.input, "output": s.output, "capability_name": s.capability_name,
            "approved": s.approved, "feedback": s.feedback, "created_at": s.created_at,
            "knowledge_refs": [UUID(r) for r in (s.knowledge_refs or [])],
        }

    def _episode_row_to_dict(self, ep: DbReasoningEpisode, steps: list[DbReasoningStep]) -> dict[str, Any]:
        return {
            "id": ep.id, "goal": ep.goal, "correlation_id": ep.correlation_id, "agent": ep.agent,
            "status": ep.status, "started_at": ep.started_at, "ended_at": ep.ended_at,
            "final_output": ep.final_output,
            "steps": [self._step_row_to_dict(s) for s in sorted(steps, key=lambda s: s.step_index)],
        }

    async def get_episode(self, episode_id: UUID) -> dict[str, Any] | None:
        stmt = select(DbReasoningEpisode).where(DbReasoningEpisode.id == episode_id)
        result = await self.session.execute(stmt)
        episode = result.scalar_one_or_none()
        if not episode:
            return None

        steps_stmt = select(DbReasoningStep).where(DbReasoningStep.episode_id == episode_id)
        steps_result = await self.session.execute(steps_stmt)
        return self._episode_row_to_dict(episode, list(steps_result.scalars().all()))

    async def get_episodes_by_node(self, node_id: UUID) -> list[dict[str, Any]]:
        contains_node = text("reasoning_steps.knowledge_refs @> CAST(:node_json AS jsonb)").bindparams(
            node_json=json.dumps([str(node_id)])
        )
        stmt = (
            select(DbReasoningStep.episode_id)
            .where(contains_node)
            .distinct()
        )
        result = await self.session.execute(stmt)
        episode_ids = [row[0] for row in result.fetchall()]

        episodes = []
        for episode_id in episode_ids:
            ep = await self.get_episode(episode_id)
            if ep:
                episodes.append(ep)
        return episodes

    async def walk_reasoning(self, node_id: UUID) -> list[dict[str, Any]]:
        contains_node = text("reasoning_steps.knowledge_refs @> CAST(:node_json AS jsonb)").bindparams(
            node_json=json.dumps([str(node_id)])
        )
        stmt = (
            select(DbReasoningStep, DbReasoningEpisode.goal, DbReasoningEpisode.agent)
            .join(DbReasoningEpisode, DbReasoningStep.episode_id == DbReasoningEpisode.id)
            .where(contains_node)
            .order_by(DbReasoningStep.created_at.asc())
        )
        result = await self.session.execute(stmt)

        steps = []
        for step, goal, agent in result.all():
            step_dict = self._step_row_to_dict(step)
            step_dict["episode_goal"] = goal
            step_dict["episode_agent"] = agent
            steps.append(step_dict)
        return steps
