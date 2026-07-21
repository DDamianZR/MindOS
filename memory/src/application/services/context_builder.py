from datetime import datetime, timezone
from uuid import UUID

from mindos_schemas.api.v1.memory_dto import ContextBundle, ContextFragment, ContextTimelineEntry

from memory.src.application.ports.database import DatabasePort
from memory.src.application.ports.embedding import EmbeddingPort
from memory.src.application.ports.vector_store import VectorStorePort

# Cantidad de hitos que se muestran en la sección temporal ("timeline corto", F1-T7).
_MAX_TIMELINE_ENTRIES = 5


class ContextBuilderService:
    """
    GraphRAG v2 (F1-T7): construye el contexto estructurado y citable que alimenta el
    razonamiento de los agentes.

    Combina:
    1. Similitud vectorial directa (top-k semillas).
    2. Expansión por grafo desde esas semillas (vecinos hasta `depth`), heredando una
       similitud descontada (`graph_expansion_decay`) — un nodo relevante conectado a algo
       ya relevante también es candidato, aunque no haya matcheado el vector directamente.
    3. Reranking por combinación lineal: similitud + importancia + recencia + confianza.
    4. Una línea temporal corta y las relaciones conceptuales asociadas, en texto legible.

    Cada fragmento devuelto lleva `node_id`/`version`/`source_id` para que el agente pueda
    citar su origen ("según [n1]...") y el resultado sea trazable hasta la fuente.
    """
    def __init__(
        self,
        vector_store: VectorStorePort,
        database: DatabasePort,
        embedding: EmbeddingPort,
        weight_similarity: float = 0.5,
        weight_importance: float = 0.2,
        weight_recency: float = 0.15,
        weight_confidence: float = 0.15,
        recency_halflife_days: float = 30.0,
        graph_expansion_decay: float = 0.7,
    ):
        self.vector_store = vector_store
        self.database = database
        self.embedding = embedding
        self.weight_similarity = weight_similarity
        self.weight_importance = weight_importance
        self.weight_recency = weight_recency
        self.weight_confidence = weight_confidence
        self.recency_halflife_days = recency_halflife_days
        self.graph_expansion_decay = graph_expansion_decay

    def _recency_score(self, created_at: datetime) -> float:
        """Decaimiento exponencial por antigüedad: 1.0 recién creado, 0.5 a `recency_halflife_days`."""
        if self.recency_halflife_days <= 0:
            return 1.0
        now = datetime.now(timezone.utc)
        age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
        return 0.5 ** (age_days / self.recency_halflife_days)

    async def build_context(self, query: str, limit: int = 5, depth: int = 1) -> ContextBundle:
        query_vector = await self.embedding.embed_query(query)
        search_results = await self.vector_store.search(query_vector, limit=limit)

        # node_id -> (similitud_heredada, via_graph). Las semillas vectoriales entran primero
        # con via_graph=False; la expansión por grafo solo puede AÑADIR nodos o mejorar su
        # score, nunca "quitarle" a un hit directo su condición de hallado directamente.
        candidates: dict[UUID, tuple[float, bool]] = {}
        for res in search_results:
            try:
                node_id = UUID(res.id)
            except ValueError:
                continue
            similarity = max(0.0, res.score)
            prev = candidates.get(node_id)
            if prev is None or similarity > prev[0]:
                candidates[node_id] = (similarity, False)

        # Expansión por grafo desde cada semilla, deduplicando nodos y aristas ya vistos.
        relation_edges: dict[tuple[UUID, UUID, str], dict] = {}
        for seed_id, (seed_similarity, _) in list(candidates.items()):
            relations = await self.database.query_relations_recursive(seed_id, max_depth=depth)
            for rel in relations:
                edge_key = (rel["source_id"], rel["target_id"], rel["relation_type"])
                relation_edges[edge_key] = rel

                inherited = seed_similarity * self.graph_expansion_decay
                target_id = rel["target_id"]
                prev = candidates.get(target_id)
                if prev is None or inherited > prev[0]:
                    candidates[target_id] = (inherited, prev[1] if prev else True)

        # Resolver la versión activa de cada candidato (F1-T4: excluye archivados por defecto)
        # y calcular el score combinado.
        version_cache: dict[UUID, dict] = {}
        scored: list[tuple[float, UUID, dict, float, bool]] = []
        for node_id, (similarity, via_graph) in candidates.items():
            ver = await self.database.get_latest_node_version(node_id)
            if not ver:
                continue
            version_cache[node_id] = ver

            importance = ver.get("importance", 0.5)
            confidence = ver.get("confidence", 0.5)
            recency = self._recency_score(ver["created_at"])
            score = (
                self.weight_similarity * similarity
                + self.weight_importance * importance
                + self.weight_recency * recency
                + self.weight_confidence * confidence
            )
            scored.append((score, node_id, ver, similarity, via_graph))

        # Ordenar por score combinado y truncar al límite final solicitado.
        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[:limit]

        fragments = [
            ContextFragment(
                citation_label=f"n{i + 1}",
                node_id=node_id,
                version=ver["version"],
                title=ver["title"],
                content=ver["content"],
                object_type=ver.get("object_type"),
                source_id=ver.get("provenance_source_id"),
                score=round(score, 4),
                similarity=round(similarity, 4),
                importance=ver.get("importance", 0.5),
                confidence=ver.get("confidence", 0.5),
                recency=round(self._recency_score(ver["created_at"]), 4),
                via_graph=via_graph,
            )
            for i, (score, node_id, ver, similarity, via_graph) in enumerate(top)
        ]

        # Timeline corto: los mismos fragmentos seleccionados, ordenados por fecha de creación.
        timeline_source = sorted(
            ((f.node_id, version_cache[f.node_id]) for f in fragments),
            key=lambda pair: pair[1]["created_at"],
            reverse=True,
        )
        timeline = [
            ContextTimelineEntry(node_id=nid, version=v["version"], title=v["title"], created_at=v["created_at"])
            for nid, v in timeline_source[:_MAX_TIMELINE_ENTRIES]
        ]

        # Relaciones legibles: solo las aristas con al menos un extremo entre los fragmentos finales.
        final_ids = {f.node_id for f in fragments}
        relations_summary = []
        for (src_id, tgt_id, relation_type), _rel in relation_edges.items():
            if src_id not in final_ids and tgt_id not in final_ids:
                continue
            src_ver = version_cache.get(src_id) or await self.database.get_latest_node_version(src_id)
            tgt_ver = version_cache.get(tgt_id) or await self.database.get_latest_node_version(tgt_id)
            src_title = src_ver["title"] if src_ver else str(src_id)
            tgt_title = tgt_ver["title"] if tgt_ver else str(tgt_id)
            relations_summary.append(f"- {src_title} ==[{relation_type}]==> {tgt_title}")

        return ContextBundle(
            query=query,
            fragments=fragments,
            timeline=timeline,
            relations_summary=relations_summary,
        )
