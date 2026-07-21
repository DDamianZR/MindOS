"""F2-T5: sembrando dos hechos opuestos se crea una arista CONTRADICTS entre ellos y
/cognitive/contradictions la lista.

El wiring (relación creada, evento emitido, formato correcto) se prueba con un LLM falso
controlable (determinista, sin red) y el umbral de similitud bajado a 0: `MockEmbedding` es
un hash determinista por texto EXACTO (no un embedding semántico), así que dos afirmaciones
DISTINTAS ("443" vs "8080") no producen similitud realista entre sí — bajar el umbral aísla
"¿el veredicto del LLM se traduce correctamente en el grafo?" de "¿el embedding identifica
bien que el par es afín?" (esto último se prueba aparte, con Ollama real, en el test de
integración de más abajo, que sí usa embeddings reales)."""
import httpx
import pytest
from fastapi.testclient import TestClient

from memory.src import main as memory_main
from memory.src.application.ports.llm import LlmPort
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_thinking_graph import InMemoryThinkingGraph
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding
from memory.src.infrastructure.adapters.ollama_embedding import OllamaEmbedding
from memory.src.infrastructure.adapters.ollama_llm import OllamaLlm


class _NoopBus:
    def __init__(self):
        self.published = []

    async def publish(self, stream_name, event_type, event_data, correlation_id):
        self.published.append({"type": event_type, "data": event_data})
        return "0-1"

    async def close(self):
        pass


class _ScriptedLlm(LlmPort):
    """Test double: siempre responde lo mismo (sin red, determinista)."""
    def __init__(self, contradicts: bool = True, confidence: float = 0.9):
        self.contradicts = contradicts
        self.confidence = confidence
        self.calls = 0

    async def generate(self, prompt, system_instruction=None, json_mode=False):
        self.calls += 1
        return (
            '{"contradicts": ' + ("true" if self.contradicts else "false") + ", "
            f'"rationale": "Ambas afirmaciones asignan valores distintos al mismo puerto.", '
            f'"confidence": {self.confidence}}}'
        )

    async def chat(self, messages, json_mode=False):
        return await self.generate(messages[-1]["content"] if messages else "", json_mode=json_mode)


def _fresh_client(monkeypatch, llm=None, embedding=None, similarity_threshold=0.0):
    monkeypatch.setattr(memory_main, "embedding_provider", embedding or MockEmbedding(768))
    monkeypatch.setattr(memory_main, "llm_provider", llm or _ScriptedLlm())
    monkeypatch.setattr(memory_main.settings, "CONTRADICTION_SIMILARITY_THRESHOLD", similarity_threshold)
    bus = _NoopBus()
    monkeypatch.setattr(memory_main, "event_bus", bus)
    monkeypatch.setattr(memory_main, "in_memory_db", InMemoryDatabase())
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    monkeypatch.setattr(memory_main, "in_memory_thinking_graph", InMemoryThinkingGraph())
    return TestClient(memory_main.app), bus


def _ingest_fact(client, content, **extra):
    resp = client.post("/api/v1/memory/ingest", json={
        "object_type": "fact", "title": content[:30], "content": content, "author": "damian", **extra,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["node_id"]


def test_on_ingest_detects_contradiction_and_creates_relation(monkeypatch):
    client, bus = _fresh_client(monkeypatch)

    node_a = _ingest_fact(client, "El puerto configurado es 443.")
    node_b = _ingest_fact(client, "El puerto configurado es 8080.")

    neighbors = client.get(f"/api/v1/memory/node/{node_b}/neighbors")
    assert neighbors.status_code == 200, neighbors.text
    edges = neighbors.json()["neighbors"]
    contradicts_edges = [e for e in edges if e["relation_type"] == "CONTRADICTS"]
    assert len(contradicts_edges) == 1
    assert contradicts_edges[0]["target_id"] == node_a

    assert any(p["type"] == "com.mindos.memory.contradiction.detected" for p in bus.published)


def test_cognitive_contradictions_lists_the_detected_pair(monkeypatch):
    client, _ = _fresh_client(monkeypatch)
    _ingest_fact(client, "El puerto configurado es 443.")
    _ingest_fact(client, "El puerto configurado es 8080.")

    resp = client.get("/api/v1/cognitive/contradictions", params={"topic": "puerto configurado"})
    assert resp.status_code == 200, resp.text
    pairs = resp.json()["contradictions"]
    assert len(pairs) == 1
    assert "puerto" in pairs[0]["rationale"].lower()
    assert pairs[0]["confidence"] == 0.9


def test_non_contradicting_facts_create_no_relation(monkeypatch):
    """Si el LLM dice que NO contradice, no debe crearse ninguna arista CONTRADICTS,
    incluso con similitud forzada a considerar el par (umbral en 0)."""
    client, bus = _fresh_client(monkeypatch, llm=_ScriptedLlm(contradicts=False))

    _ingest_fact(client, "El puerto configurado es 443.")
    node_b = _ingest_fact(client, "El servicio de logging usa el puerto 9200.")

    neighbors = client.get(f"/api/v1/memory/node/{node_b}/neighbors")
    assert neighbors.json()["neighbors"] == []
    assert not any(p["type"] == "com.mindos.memory.contradiction.detected" for p in bus.published)


def test_notes_do_not_trigger_contradiction_check(monkeypatch):
    """El chequeo on-ingest solo aplica a fact/hypothesis, no a notas genéricas."""
    scripted = _ScriptedLlm(contradicts=True)
    client, _ = _fresh_client(monkeypatch, llm=scripted)

    client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "n1", "content": "El puerto configurado es 443.", "author": "damian",
    })
    client.post("/api/v1/memory/ingest", json={
        "object_type": "note", "title": "n2", "content": "El puerto configurado es 8080.", "author": "damian",
    })
    assert scripted.calls == 0, "no debe consultarse al LLM para notas genéricas"


def test_batch_scan_detects_contradictions_among_existing_facts(monkeypatch):
    """Modo batch (F2-T5): /contradictions/scan recorre los nodos activos recientes y
    confirma contradicciones igual que el chequeo on-ingest."""
    client, bus = _fresh_client(monkeypatch)
    _ingest_fact(client, "El límite de usuarios concurrentes es 100.")
    _ingest_fact(client, "El límite de usuarios concurrentes es 500.")

    # Ambos ya se compararon on-ingest; limpiamos el bus para aislar lo que aporta el batch.
    bus.published.clear()

    scan = client.post("/api/v1/memory/contradictions/scan")
    assert scan.status_code == 200, scan.text
    body = scan.json()
    assert body["nodes_checked"] == 2
    # Ya estaba detectada por on-ingest; el batch la vuelve a confirmar (no es idempotente por
    # diseño simple de v1) — lo relevante es que la cobertura batch funciona sin lanzar excepciones.
    assert body["contradictions_detected"] >= 1


@pytest.mark.integration
def test_real_embeddings_and_llm_confirm_port_contradiction(monkeypatch):
    """
    DoD F2-T5 con el stack real: Ollama para embeddings (identifica que el par es afín, sin
    bajar el umbral) Y para el juicio de contradicción (qwen3:8b). Verifica el flujo completo
    tal como correría en producción, no solo el wiring con dobles de prueba.
    """
    try:
        httpx.get("http://localhost:11434/api/tags", timeout=2.0)
    except Exception:
        pytest.skip("Ollama no está corriendo en localhost:11434")

    real_embedding = OllamaEmbedding("http://localhost:11434", "nomic-embed-text")
    real_llm = OllamaLlm("qwen3:8b", "http://localhost:11434")
    client, _ = _fresh_client(
        monkeypatch, llm=real_llm, embedding=real_embedding,
        similarity_threshold=0.65,  # el umbral real de settings, sin atajos
    )

    # El context manager mantiene un único event loop para las 3 peticiones: los clientes
    # httpx reales (embedding + LLM) quedan atados a esa conexión y no se pueden reutilizar
    # entre loops distintos (cada TestClient.request() sin `with` abre uno nuevo).
    with client:
        node_a = _ingest_fact(client, "El puerto configurado para el servidor es 443.")
        node_b = _ingest_fact(client, "El puerto configurado para el servidor es 8080.")
        neighbors = client.get(f"/api/v1/memory/node/{node_b}/neighbors")

    edges = [e for e in neighbors.json()["neighbors"] if e["relation_type"] == "CONTRADICTS"]
    assert len(edges) == 1, "embeddings + LLM reales deberían confirmar que 443 y 8080 se contradicen"
    assert edges[0]["target_id"] == node_a
