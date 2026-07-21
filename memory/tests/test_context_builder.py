from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from memory.src.application.ports.database import DatabasePort
from memory.src.application.ports.embedding import EmbeddingPort
from memory.src.application.ports.vector_store import VectorSearchResult, VectorStorePort
from memory.src.application.services.context_builder import ContextBuilderService

NOW = datetime.now(timezone.utc)


# Mock concreto para el Vector Store Port
class DummyVectorStore(VectorStorePort):
    def __init__(self, search_results):
        self.results = search_results

    async def upsert(self, vector_id, embedding, payload): pass
    async def search(self, query_embedding, limit, filters=None):
        return self.results[:limit]


# Mock concreto para la Base de Datos
class DummyDatabase(DatabasePort):
    def __init__(self, node_versions, relations):
        self.node_versions = node_versions
        self.relations = relations

    async def save_node(self, node_id, object_type): pass
    async def save_node_version(self, node_id, version_id, version, title, content, author, metadata,
                                 parent_version_id=None, confidence=0.5, importance=0.5,
                                 status="active", evidence=None, provenance_source_id=None): pass
    async def get_latest_node_version(self, node_id, include_archived=False):
        return self.node_versions.get(node_id)
    async def find_source_by_kind_uri(self, kind, uri): return None
    async def save_source(self, source_id, kind, uri, raw_ref, metadata): pass
    async def get_source(self, source_id): return None
    async def get_node_versions(self, node_id):
        return [self.node_versions.get(node_id)] if node_id in self.node_versions else []
    async def get_node_version_asof(self, node_id, at):
        return self.node_versions.get(node_id)
    async def set_latest_version_tombstone(self, node_id, tombstoned): return node_id in self.node_versions
    async def save_relation(self, source_id, target_id, relation_type, metadata): pass
    async def delete_relation(self, source_id, target_id, relation_type): pass
    async def query_relations_recursive(self, start_node_id, max_depth):
        return [r for r in self.relations if r["source_id"] == start_node_id]
    async def query_relations_asof(self, start_node_id, at, max_depth):
        return [r for r in self.relations if r["source_id"] == start_node_id]
    async def save_event_log(self, event_id, event_type, payload): pass


# Mock concreto para los Embeddings
class DummyEmbedding(EmbeddingPort):
    async def embed_query(self, text):
        return [0.1, 0.2, 0.3]
    async def embed_documents(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


def _version(node_id, title, content, importance=0.5, confidence=0.5, created_at=NOW, object_type="note"):
    return {
        "node_id": node_id, "version": 1, "title": title, "content": content,
        "author": "damian", "created_at": created_at, "parent_version_id": None,
        "object_type": object_type, "importance": importance, "confidence": confidence,
        "evidence": [], "salience": 0.5, "tombstoned_at": None, "provenance_source_id": None,
    }


@pytest.mark.asyncio
async def test_build_context_returns_citable_fragments_and_graph_relations():
    node_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414900")
    target_node_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414901")

    search_results = [VectorSearchResult(id=str(node_id), score=0.95, payload={"type": "note"})]
    node_versions = {
        node_id: _version(node_id, "Nota de Configuración", "Contenido de la nota"),
        target_node_id: _version(target_node_id, "Documento Docker", "Contenido de docker"),
    }
    relations = [{
        "source_id": node_id, "target_id": target_node_id, "relation_type": "BELONGS_TO",
        "valid_from": NOW, "valid_to": None, "metadata": {},
    }]

    service = ContextBuilderService(DummyVectorStore(search_results), DummyDatabase(node_versions, relations),
                                     DummyEmbedding())
    bundle = await service.build_context("consulta de prueba", limit=5, depth=1)

    # El hit vectorial directo queda como fragmento citable
    assert len(bundle.fragments) >= 1
    direct = bundle.citations["n1"]
    assert direct.node_id == node_id
    assert direct.title == "Nota de Configuración"
    assert direct.via_graph is False

    # El vecino de grafo (Documento Docker) también entra como fragmento, vía expansión
    graph_fragment = next((f for f in bundle.fragments if f.node_id == target_node_id), None)
    assert graph_fragment is not None
    assert graph_fragment.via_graph is True

    # Relaciones legibles y prompt final con marcadores de cita
    assert "- Nota de Configuración ==[BELONGS_TO]==> Documento Docker" in bundle.relations_summary
    prompt = bundle.to_prompt()
    assert "[n1]" in prompt
    assert "Nota de Configuración" in prompt


@pytest.mark.asyncio
async def test_high_importance_node_ranks_above_low_importance_node():
    """DoD F1-T7: un nodo de alta importance sube en el ranking frente a uno de baja,
    incluso con similitud vectorial idéntica."""
    important_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414910")
    unimportant_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414911")

    # Misma similitud vectorial (0.8) para ambos: la diferencia de ranking debe venir SOLO
    # de importance (0.95 vs 0.05), no de la búsqueda vectorial.
    search_results = [
        VectorSearchResult(id=str(unimportant_id), score=0.8, payload={}),
        VectorSearchResult(id=str(important_id), score=0.8, payload={}),
    ]
    node_versions = {
        important_id: _version(important_id, "Decisión crítica de arquitectura", "contenido A", importance=0.95),
        unimportant_id: _version(unimportant_id, "Nota trivial", "contenido B", importance=0.05),
    }

    service = ContextBuilderService(DummyVectorStore(search_results), DummyDatabase(node_versions, []),
                                     DummyEmbedding())
    bundle = await service.build_context("consulta", limit=2, depth=0)

    assert len(bundle.fragments) == 2
    assert bundle.fragments[0].node_id == important_id, "el nodo de alta importancia debe rankear primero"
    assert bundle.fragments[0].score > bundle.fragments[1].score


@pytest.mark.asyncio
async def test_recency_decay_favors_recent_node_over_old_one():
    recent_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414920")
    old_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414921")

    search_results = [
        VectorSearchResult(id=str(recent_id), score=0.7, payload={}),
        VectorSearchResult(id=str(old_id), score=0.7, payload={}),
    ]
    node_versions = {
        recent_id: _version(recent_id, "Reciente", "c", created_at=NOW),
        old_id: _version(old_id, "Antiguo", "c", created_at=NOW - timedelta(days=365)),
    }

    service = ContextBuilderService(DummyVectorStore(search_results), DummyDatabase(node_versions, []),
                                     DummyEmbedding(), recency_halflife_days=30.0)
    bundle = await service.build_context("consulta", limit=2, depth=0)

    assert bundle.fragments[0].node_id == recent_id
    assert bundle.fragments[0].recency > bundle.fragments[1].recency


@pytest.mark.asyncio
async def test_archived_node_excluded_from_context():
    """F1-T4: el Context Builder excluye por defecto los nodos archivados (tombstoneados)."""
    node_id = UUID("018b10f8-e1a5-7b18-b2a6-382a93414930")
    search_results = [VectorSearchResult(id=str(node_id), score=0.9, payload={})]

    class ArchivedDatabase(DummyDatabase):
        async def get_latest_node_version(self, node_id, include_archived=False):
            return None  # simula un nodo cuya última versión está tombstoneada

    service = ContextBuilderService(DummyVectorStore(search_results), ArchivedDatabase({}, []), DummyEmbedding())
    bundle = await service.build_context("consulta", limit=5, depth=0)

    assert bundle.fragments == []
