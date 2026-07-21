import json
from typing import Any
from uuid import UUID

from mindos_common.logging import get_logger
from mindos_schemas.domain import ObjectType

from memory.src.application.ports.database import DatabasePort
from memory.src.application.ports.embedding import EmbeddingPort
from memory.src.application.ports.llm import LlmPort
from memory.src.application.ports.vector_store import VectorStorePort

logger = get_logger("contradiction_detector")

CONTRADICTS = "CONTRADICTS"

# Tipos "afirmación" entre los que una contradicción lógica tiene sentido. Se usa tanto para
# decidir qué nodos disparan el chequeo on-ingest (main.py) como para filtrar candidatos aquí:
# comparar un `fact` contra una `idea`/`decision` no comparable generaría CONTRADICTS espurios
# (bug encontrado en el smoke test de cierre de Fase 2, ver plan/NOTAS.md).
CONTRADICTABLE_TYPES = {ObjectType.FACT, ObjectType.HYPOTHESIS}


class ContradictionDetectorService:
    """
    Detección de contradicciones (F2-T5): "¿qué contradicciones existen en mi conocimiento?".

    Evita falsos positivos con dos filtros en cascada:
    1. Similitud vectorial mínima (`similarity_threshold`) — descarta pares sin relación temática.
    2. Confirmación del LLM — la similitud semántica NO distingue "mismo tema, compatible" de
       "mismo tema, contradictorio" (medido empíricamente: ambos casos caen ~0.77-0.90 de
       similitud coseño con nomic-embed-text); solo el LLM puede juzgar la lógica.

    Falla de forma segura: si el LLM no responde o responde algo inválido, NO se crea ninguna
    arista `CONTRADICTS` (mejor un falso negativo silencioso que un falso positivo auditable).
    """
    def __init__(self, database: DatabasePort, vector_store: VectorStorePort, embedding: EmbeddingPort, llm: LlmPort):
        self.database = database
        self.vector_store = vector_store
        self.embedding = embedding
        self.llm = llm

    async def _ask_llm_for_contradiction(self, content_a: str, content_b: str) -> dict[str, Any]:
        prompt = (
            "Actúa como un detector de contradicciones lógicas para un sistema de conocimiento personal.\n\n"
            f"Afirmación A: {content_a}\n"
            f"Afirmación B: {content_b}\n\n"
            "¿Estas dos afirmaciones se CONTRADICEN entre sí, es decir, no pueden ser ambas "
            "ciertas al mismo tiempo? Dos afirmaciones que simplemente tratan el mismo tema sin "
            "negarse entre sí (una complementa o elabora sobre la otra) NO son una contradicción.\n\n"
            "Responde OBLIGATORIAMENTE en JSON con esta estructura exacta:\n"
            '{"contradicts": true o false, "rationale": "explicación breve", "confidence": 0.0 a 1.0}'
        )
        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            data = json.loads(response_text)
            return {
                "contradicts": bool(data.get("contradicts", False)),
                "rationale": str(data.get("rationale", "")),
                "confidence": float(data.get("confidence", 0.5)),
            }
        except Exception as e:
            logger.warning("Fallo evaluando contradicción con el LLM; se descarta el candidato", error=str(e))
            return {"contradicts": False, "rationale": "", "confidence": 0.0}

    async def check_node_for_contradictions(
        self, node_id: UUID, top_k: int = 5, similarity_threshold: float = 0.65
    ) -> list[dict[str, Any]]:
        """
        Modo on-ingest (F2-T5): compara un nodo contra sus `top_k` vecinos semánticos más
        similares y crea una arista `CONTRADICTS` (con rationale/confidence en metadata) por
        cada par que el LLM confirme. Devuelve las contradicciones detectadas en esta corrida.
        """
        node_ver = await self.database.get_latest_node_version(node_id)
        if not node_ver:
            return []

        query_vector = await self.embedding.embed_query(node_ver["content"])
        candidates = await self.vector_store.search(query_vector, limit=top_k + 1)  # +1: puede incluirse a sí mismo

        detected = []
        for res in candidates:
            try:
                candidate_id = UUID(res.id)
            except ValueError:
                continue
            if candidate_id == node_id or res.score < similarity_threshold:
                continue

            candidate_ver = await self.database.get_latest_node_version(candidate_id)
            if not candidate_ver or candidate_ver.get("object_type") not in CONTRADICTABLE_TYPES:
                continue

            verdict = await self._ask_llm_for_contradiction(node_ver["content"], candidate_ver["content"])
            if not verdict["contradicts"]:
                continue

            metadata = {"rationale": verdict["rationale"], "confidence": verdict["confidence"]}
            await self.database.save_relation(
                source_id=node_id, target_id=candidate_id, relation_type=CONTRADICTS, metadata=metadata,
            )
            logger.info(
                "Contradicción detectada", node_a=str(node_id), node_b=str(candidate_id),
                confidence=verdict["confidence"]
            )
            detected.append({"node_a_id": node_id, "node_b_id": candidate_id, **metadata})

        return detected

    async def run_batch(
        self, limit: int = 200, top_k: int = 5, similarity_threshold: float = 0.65
    ) -> dict[str, Any]:
        """Modo batch (F2-T5): recorre los nodos activos más recientes buscando contradicciones."""
        versions = await self.database.list_node_versions_since(since=None, limit=limit)
        total_detected: list[dict[str, Any]] = []
        for ver in versions:
            detected = await self.check_node_for_contradictions(
                ver["node_id"], top_k=top_k, similarity_threshold=similarity_threshold
            )
            total_detected.extend(detected)
        return {"nodes_checked": len(versions), "contradictions": total_detected}
