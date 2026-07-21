from uuid import UUID

from memory.src.application.ports.database import DatabasePort
from memory.src.application.ports.embedding import EmbeddingPort
from memory.src.application.ports.vector_store import VectorStorePort


class ContextBuilderService:
    """
    Servicio de dominio/aplicación encargado de construir el contexto estructurado
    para alimentar el razonamiento de los agentes.
    Combina RAG vectorial + relaciones semánticas del grafo + metadatos.
    """
    def __init__(
        self,
        vector_store: VectorStorePort,
        database: DatabasePort,
        embedding: EmbeddingPort
    ):
        self.vector_store = vector_store
        self.database = database
        self.embedding = embedding

    async def build_context(self, query: str, limit: int = 3, max_depth: int = 1) -> str:
        # 1. Obtener vector de la consulta
        query_vector = await self.embedding.embed_query(query)

        # 2. Buscar nodos similares en el almacén vectorial
        search_results = await self.vector_store.search(query_vector, limit=limit)

        context_parts = []
        context_parts.append("=== CONTEXTO SEMÁNTICO DIRECTO ===")

        related_node_ids = []
        for idx, res in enumerate(search_results):
            try:
                node_id = UUID(res.id)
                related_node_ids.append(node_id)

                # Obtener la versión más reciente del nodo
                ver = await self.database.get_latest_node_version(node_id)
                if ver:
                    context_parts.append(
                        f"[{idx+1}] Nodo: {ver['title']} (Tipo: {res.payload.get('type')})\n"
                        f"Contenido: {ver['content']}\n"
                        f"Fecha: {ver['created_at'].isoformat()}\n"
                    )
            except ValueError:
                # Si el ID no es un UUID válido en simulación
                context_parts.append(
                    f"[{idx+1}] Nodo ID inválido ({res.id}): {res.payload.get('title')}\n"
                )

        # 3. Traer grafo de relaciones asociadas
        context_parts.append("\n=== RELACIONES CONCEPTUALES ASOCIADAS (GRAFO) ===")
        relations_found = False

        for node_id in related_node_ids:
            relations = await self.database.query_relations_recursive(node_id, max_depth=max_depth)
            for rel in relations:
                relations_found = True

                # Intentar traer títulos de los nodos de origen y destino para legibilidad del prompt
                source_ver = await self.database.get_latest_node_version(rel["source_id"])
                target_ver = await self.database.get_latest_node_version(rel["target_id"])

                source_title = source_ver["title"] if source_ver else str(rel["source_id"])
                target_title = target_ver["title"] if target_ver else str(rel["target_id"])

                context_parts.append(
                    f"- {source_title} ==[{rel['relation_type']}]==> {target_title}"
                )

        if not relations_found:
            context_parts.append("No se detectaron relaciones conectadas de primer grado.")

        return "\n".join(context_parts)
