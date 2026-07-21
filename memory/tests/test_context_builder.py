from datetime import datetime, timezone
from uuid import UUID

import pytest

from memory.src.application.ports.database import DatabasePort
from memory.src.application.ports.embedding import EmbeddingPort
from memory.src.application.ports.vector_store import VectorSearchResult, VectorStorePort
from memory.src.application.services.context_builder import ContextBuilderService


# Mock concreto para el Vector Store Port
class DummyVectorStore(VectorStorePort):
    def __init__(self, search_results):
        self.results = search_results

    async def upsert(self, vector_id, embedding, payload): pass
    async def search(self, query_embedding, limit, filters=None):
        return self.results[:limit]
    async def delete(self, vector_id): pass


# Mock concreto para la Base de Datos
class DummyDatabase(DatabasePort):
    def __init__(self, node_versions, relations):
        self.node_versions = node_versions
        self.relations = relations

    async def save_node(self, node_id, object_type): pass
    async def save_node_version(self, node_id, version_id, version, title, content, author, metadata,
                                 parent_version_id=None, confidence=0.5, importance=0.5,
                                 status="active", evidence=None): pass
    async def get_latest_node_version(self, node_id, include_archived=False):
        return self.node_versions.get(node_id)
    async def get_node_versions(self, node_id):
        return [self.node_versions.get(node_id)] if node_id in self.node_versions else []
    async def save_relation(self, source_id, target_id, relation_type, metadata): pass
    async def delete_relation(self, source_id, target_id, relation_type): pass
    async def query_relations_recursive(self, start_node_id, max_depth):
        return [r for r in self.relations if r["source_id"] == start_node_id]
    async def save_event_log(self, event_id, event_type, payload): pass


# Mock concreto para los Embeddings
class DummyEmbedding(EmbeddingPort):
    async def embed_query(self, text):
        return [0.1, 0.2, 0.3]
    async def embed_documents(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


@pytest.mark.asyncio
async def test_build_context_success():
    # 1. Preparar datos de prueba
    node_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414900")
    target_node_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414901")

    search_results = [
        VectorSearchResult(id=str(node_id), score=0.95, payload={"type": "note"})
    ]

    node_versions = {
        node_id: {
            "node_id": node_id,
            "version": 1,
            "title": "Nota de Configuración",
            "content": "Contenido de la nota",
            "created_at": datetime.now(timezone.utc),
            "parent_version_id": None
        },
        target_node_id: {
            "node_id": target_node_id,
            "version": 1,
            "title": "Documento Docker",
            "content": "Contenido de docker",
            "created_at": datetime.now(timezone.utc),
            "parent_version_id": None
        }
    }

    relations = [
        {
            "source_id": node_id,
            "target_id": target_node_id,
            "relation_type": "BELONGS_TO",
            "valid_from": datetime.now(timezone.utc),
            "valid_to": None,
            "metadata": {}
        }
    ]

    # 2. Inicializar el servicio con sus dependencias mockeadas
    vector_store = DummyVectorStore(search_results)
    database = DummyDatabase(node_versions, relations)
    embedding = DummyEmbedding()

    context_service = ContextBuilderService(vector_store, database, embedding)

    # 3. Ejecutar y validar
    context = await context_service.build_context("consulta de prueba")

    assert "=== CONTEXTO SEMÁNTICO DIRECTO ===" in context
    assert "Nota de Configuración" in context
    assert "=== RELACIONES CONCEPTUALES ASOCIADAS (GRAFO) ===" in context
    assert "Nota de Configuración ==[BELONGS_TO]==> Documento Docker" in context
