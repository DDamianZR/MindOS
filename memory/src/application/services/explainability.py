from uuid import UUID

from mindos_schemas.api.v1.memory_dto import SourceDto
from mindos_schemas.api.v1.thinking_dto import (
    ExplainEpisodeResponse,
    ExplainEvidenceDto,
    ExplainNodeResponse,
)

from memory.src.application.ports.database import DatabasePort
from memory.src.application.ports.thinking_graph import ThinkingGraphPort
from memory.src.application.services.dto_mappers import episode_dict_to_dto

# Relaciones que cuentan como "sustento" de una conclusión al recorrer el grafo hacia atrás (F2-T3).
EXPLAIN_RELATION_TYPES = {"DECIDES", "EVIDENCES", "DERIVED_FROM", "ANSWERS"}


class ExplainabilityService:
    """
    Explicabilidad del razonamiento (F2-T3): "¿cómo llegué a esto?".

    Combina dos fuentes distintas de trazabilidad:
    1. El Knowledge Graph (`DatabasePort`): qué evidencias/decisiones/hipótesis sustentan un
       nodo, recorriendo hacia atrás las aristas DECIDES/EVIDENCES/DERIVED_FROM/ANSWERS.
    2. El Thinking Graph (`ThinkingGraphPort`): qué episodios de razonamiento (agentes)
       produjeron o citaron ese nodo.
    """
    def __init__(self, database: DatabasePort, thinking_graph: ThinkingGraphPort):
        self.database = database
        self.thinking_graph = thinking_graph

    async def explain_node(self, node_id: UUID, max_depth: int = 3) -> ExplainNodeResponse | None:
        node_ver = await self.database.get_latest_node_version(node_id, include_archived=True)
        if not node_ver:
            return None

        edges = await self.database.query_incoming_relations(node_id, max_depth=max_depth)
        relevant_edges = [e for e in edges if e["relation_type"] in EXPLAIN_RELATION_TYPES]

        # Agrupar aristas por su target_id para reconstruir el árbol de sustento por niveles.
        children_by_target: dict[UUID, list[dict]] = {}
        for edge in relevant_edges:
            children_by_target.setdefault(edge["target_id"], []).append(edge)

        version_cache: dict[UUID, dict | None] = {node_id: node_ver}

        async def get_version(nid: UUID) -> dict | None:
            if nid not in version_cache:
                version_cache[nid] = await self.database.get_latest_node_version(nid, include_archived=True)
            return version_cache[nid]

        async def source_dto_for(version: dict) -> SourceDto | None:
            source_id = version.get("provenance_source_id")
            if not source_id:
                return None
            src = await self.database.get_source(source_id)
            if not src:
                return None
            return SourceDto(
                id=src["id"], kind=src["kind"], uri=src["uri"], raw_ref=src["raw_ref"],
                captured_at=src["captured_at"], metadata=src["metadata"],
            )

        async def build_tree(current_id: UUID, visited: frozenset[UUID]) -> list[ExplainEvidenceDto]:
            result = []
            for edge in children_by_target.get(current_id, []):
                source_id = edge["source_id"]
                if source_id in visited:
                    continue  # evita ciclos (el grafo no debería tener, pero no confiar ciegamente)
                source_ver = await get_version(source_id)
                if not source_ver:
                    continue
                nested = await build_tree(source_id, visited | {source_id})
                result.append(ExplainEvidenceDto(
                    node_id=source_id, title=source_ver["title"], content=source_ver["content"],
                    object_type=source_ver.get("object_type"), relation_type=edge["relation_type"],
                    confidence=source_ver.get("confidence", 0.5), importance=source_ver.get("importance", 0.5),
                    source=await source_dto_for(source_ver), supporting=nested,
                ))
            return result

        supporting_evidence = await build_tree(node_id, frozenset({node_id}))

        episodes_raw = await self.thinking_graph.get_episodes_by_node(node_id)
        episodes = [episode_dict_to_dto(ep) for ep in episodes_raw]

        return ExplainNodeResponse(
            node_id=node_id, title=node_ver["title"], content=node_ver["content"],
            object_type=node_ver.get("object_type"),
            supporting_evidence=supporting_evidence, episodes=episodes,
        )

    async def explain_episode(self, episode_id: UUID) -> ExplainEpisodeResponse | None:
        episode = await self.thinking_graph.get_episode(episode_id)
        if not episode:
            return None

        dto = episode_dict_to_dto(episode)
        narrative = [f'Meta: "{dto.goal}"']
        for step in dto.steps:
            if step.kind in ("plan", "replan"):
                label = "Planificación" if step.kind == "plan" else "Replanificación (tras rechazo)"
                narrative.append(f"[{step.step_index}] {label}: {step.output or '(sin salida)'}")
            elif step.kind == "execute":
                capability = f" usando '{step.capability_name}'" if step.capability_name else ""
                narrative.append(f"[{step.step_index}] Ejecución{capability}: {step.output or '(sin salida)'}")
            elif step.kind == "review":
                verdict = "Aprobado" if step.approved else "Rechazado"
                detail = f" — {step.feedback}" if step.feedback else ""
                narrative.append(f"[{step.step_index}] Revisión: {verdict}{detail}")
        if dto.final_output:
            narrative.append(f"Resultado final ({dto.status}): {dto.final_output}")

        return ExplainEpisodeResponse(episode=dto, narrative=narrative)
