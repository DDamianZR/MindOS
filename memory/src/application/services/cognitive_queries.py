from datetime import datetime
from uuid import UUID

from mindos_schemas.api.v1.cognitive_dto import (
    ContradictionPair,
    ContradictionsResponse,
    DecisionItem,
    DecisionsResponse,
    PastThinkingItem,
    PastThinkingResponse,
    PatternBucket,
    PatternsResponse,
    SimilarIdeaItem,
    SimilarIdeasResponse,
    SupportResponse,
)

from memory.src.application.ports.database import DatabasePort
from memory.src.application.ports.embedding import EmbeddingPort
from memory.src.application.ports.vector_store import VectorStorePort
from memory.src.application.services.explainability import (
    SUPPORT_RELATION_TYPES,
    build_evidence_tree,
)

# Tipos de nodo que cuentan como "idea" al buscar ideas similares (F2-T4, pregunta 3).
IDEA_LIKE_TYPES = {"idea", "hypothesis"}

# Sobre-muestreo del vector store: se piden más candidatos de los que se devuelven, ya que
# varios pasos posteriores (as-of, filtro por tipo, exclusión de archivados) descartan algunos.
_OVERFETCH_FACTOR = 4


class CognitiveQueryService:
    """
    Cognitive Query API (F2-T4): las 7 preguntas insignia de la visión de MindOS, como
    consultas de primera clase. "¿Cómo llegué a esta conclusión?" no vive aquí — reutiliza
    `/explain/{node_id}` (F2-T3, `ExplainabilityService`) directamente.
    """
    def __init__(self, database: DatabasePort, vector_store: VectorStorePort, embedding: EmbeddingPort):
        self.database = database
        self.vector_store = vector_store
        self.embedding = embedding

    async def past_thinking(self, topic: str, at: datetime, limit: int = 5) -> PastThinkingResponse:
        """¿Qué pensaba en la fecha `at` sobre `topic`? Búsqueda semántica + reconstrucción as-of."""
        query_vector = await self.embedding.embed_query(topic)
        candidates = await self.vector_store.search(query_vector, limit=limit * _OVERFETCH_FACTOR)

        items = []
        for res in candidates:
            if len(items) >= limit:
                break
            try:
                node_id = UUID(res.id)
            except ValueError:
                continue
            ver = await self.database.get_node_version_asof(node_id, at)
            if not ver:
                continue  # el nodo no existía (o no tenía contenido aún) en esa fecha
            items.append(PastThinkingItem(
                node_id=node_id, title=ver["title"], content=ver["content"], version=ver["version"],
                object_type=ver.get("object_type"), similarity=max(0.0, res.score),
                as_of_created_at=ver["created_at"],
            ))
        return PastThinkingResponse(topic=topic, at=at, items=items)

    async def similar(self, node_id: UUID, limit: int = 5) -> SimilarIdeasResponse | None:
        """¿Qué ideas similares tuve antes? KNN sobre object_type in (idea, hypothesis)."""
        ref_ver = await self.database.get_latest_node_version(node_id, include_archived=True)
        if not ref_ver:
            return None

        query_vector = await self.embedding.embed_query(ref_ver["content"])
        candidates = await self.vector_store.search(query_vector, limit=(limit + 1) * _OVERFETCH_FACTOR)

        items = []
        for res in candidates:
            if len(items) >= limit:
                break
            try:
                candidate_id = UUID(res.id)
            except ValueError:
                continue
            if candidate_id == node_id:
                continue
            ver = await self.database.get_latest_node_version(candidate_id)
            if not ver or ver.get("object_type") not in IDEA_LIKE_TYPES:
                continue
            items.append(SimilarIdeaItem(
                node_id=candidate_id, title=ver["title"], content=ver["content"],
                object_type=ver["object_type"], similarity=max(0.0, res.score), created_at=ver["created_at"],
            ))
        items.sort(key=lambda i: i.created_at, reverse=True)
        return SimilarIdeasResponse(node_id=node_id, items=items)

    async def decisions(self, topic: str, limit: int = 5) -> DecisionsResponse:
        """¿Qué decisiones tomé y por qué? Nodos `decision` + su evidencia + rationale."""
        query_vector = await self.embedding.embed_query(topic)
        candidates = await self.vector_store.search(query_vector, limit=limit * _OVERFETCH_FACTOR)

        result = []
        for res in candidates:
            if len(result) >= limit:
                break
            try:
                node_id = UUID(res.id)
            except ValueError:
                continue
            ver = await self.database.get_latest_node_version(node_id)
            if not ver or ver.get("object_type") != "decision":
                continue

            outgoing = await self.database.query_relations_recursive(node_id, max_depth=1)
            decides_ids = [r["target_id"] for r in outgoing if r["relation_type"] == "DECIDES"]
            incoming = await self.database.query_incoming_relations(node_id, max_depth=1)
            evidence_ids = [r["source_id"] for r in incoming if r["relation_type"] in SUPPORT_RELATION_TYPES]

            result.append(DecisionItem(
                node_id=node_id, title=ver["title"], content=ver["content"],
                rationale=(ver.get("metadata") or {}).get("rationale"), created_at=ver["created_at"],
                evidence_node_ids=evidence_ids, decides_node_ids=decides_ids,
            ))
        return DecisionsResponse(topic=topic, decisions=result)

    async def support(self, node_id: UUID, max_depth: int = 3) -> SupportResponse | None:
        """¿Qué respalda esta recomendación? Cadena SUPPORTS/EVIDENCES + provenance."""
        node_ver, tree = await build_evidence_tree(self.database, node_id, SUPPORT_RELATION_TYPES, max_depth)
        if not node_ver:
            return None
        return SupportResponse(
            node_id=node_id, title=node_ver["title"], content=node_ver["content"],
            object_type=node_ver.get("object_type"), support=tree,
        )

    async def contradictions(self, topic: str, limit: int = 10) -> ContradictionsResponse:
        """¿Qué contradicciones existen en mi conocimiento sobre `topic`? Aristas CONTRADICTS (F2-T5)."""
        query_vector = await self.embedding.embed_query(topic)
        candidates = await self.vector_store.search(query_vector, limit=limit * _OVERFETCH_FACTOR)

        seen_pairs: set[frozenset[UUID]] = set()
        pairs = []
        for res in candidates:
            if len(pairs) >= limit:
                break
            try:
                node_id = UUID(res.id)
            except ValueError:
                continue
            if not await self.database.get_latest_node_version(node_id):
                continue

            outgoing = await self.database.query_relations_recursive(node_id, max_depth=1)
            incoming = await self.database.query_incoming_relations(node_id, max_depth=1)
            edges = (
                [(node_id, r["target_id"], r) for r in outgoing if r["relation_type"] == "CONTRADICTS"] +
                [(r["source_id"], node_id, r) for r in incoming if r["relation_type"] == "CONTRADICTS"]
            )
            for node_a_id, node_b_id, rel in edges:
                pair_key = frozenset({node_a_id, node_b_id})
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                ver_a = await self.database.get_latest_node_version(node_a_id, include_archived=True)
                ver_b = await self.database.get_latest_node_version(node_b_id, include_archived=True)
                if not ver_a or not ver_b:
                    continue
                rel_metadata = rel.get("metadata") or {}
                pairs.append(ContradictionPair(
                    node_a_id=node_a_id, node_a_title=ver_a["title"],
                    node_b_id=node_b_id, node_b_title=ver_b["title"],
                    rationale=rel_metadata.get("rationale"), confidence=rel_metadata.get("confidence"),
                ))
        return ContradictionsResponse(topic=topic, contradictions=pairs)

    async def patterns(self, limit: int = 500) -> PatternsResponse:
        """¿Qué patrones aparecen en mi forma de pensar? v1: temas/tipos más frecuentes por periodo."""
        versions = await self.database.list_node_versions_since(since=None, limit=limit)

        bucket_counts: dict[tuple[str, str], int] = {}
        type_counts: dict[str, int] = {}
        for ver in versions:
            period = ver["created_at"].strftime("%Y-%m")
            object_type = ver.get("object_type") or "unknown"
            bucket_counts[(period, object_type)] = bucket_counts.get((period, object_type), 0) + 1
            type_counts[object_type] = type_counts.get(object_type, 0) + 1

        buckets = [
            PatternBucket(period=period, object_type=object_type, count=count)
            for (period, object_type), count in bucket_counts.items()
        ]
        buckets.sort(key=lambda b: (b.period, -b.count))

        most_common_type = max(type_counts, key=lambda t: type_counts[t]) if type_counts else None

        return PatternsResponse(buckets=buckets, total_nodes=len(versions), most_common_type=most_common_type)
