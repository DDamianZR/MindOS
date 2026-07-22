"""
F3-T5: pipeline de ingestión — por cada MessageReceivedEvent (CLI/REST/WhatsApp), determina el
tipo de contenido, resuelve binarios (Storage+OCR/STT), ingiere con provenance real (vía el
propio /memory/ingest, dedup F1-T5 incluido), propone relaciones por similitud, y dispara un
agente si es una pregunta.

Se prueba `IngestionPipelineService.handle_event` directamente (sin pasar por
`RedisEventBus.subscribe`, que no está disponible en este entorno de desarrollo) — mismo
patrón que el resto de tests de servicios de esta fase.
"""
import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from mindos_common.ids import new_id

from memory.src import main as memory_main
from memory.src.application.ports.llm import LlmPort
from memory.src.application.services.ingestion_pipeline import IngestionPipelineService
from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase
from memory.src.infrastructure.adapters.in_memory_storage import InMemoryStorage
from memory.src.infrastructure.adapters.in_memory_thinking_graph import InMemoryThinkingGraph
from memory.src.infrastructure.adapters.in_memory_vector_store import InMemoryVectorStore
from memory.src.infrastructure.adapters.mock_embedding import MockEmbedding
from memory.src.infrastructure.adapters.mock_ocr import MockOcr
from memory.src.infrastructure.adapters.mock_stt import MockStt


class _NoopBus:
    async def publish(self, *args, **kwargs):
        return "0-1"

    async def close(self):
        pass


class _ScriptedLlm(LlmPort):
    """
    Test double determinista: distingue el prompt de clasificación de pregunta (F3-T5 paso 6)
    del prompt de auto-enlazado (paso 4) por una palabra clave de cada uno, y responde según lo
    configurado — sin red, sin ambigüedad entre los dos usos del mismo `llm_provider`.
    """
    def __init__(self, is_question: bool = False, related: bool = False, relation_type: str = "RELATED_TO"):
        self.is_question = is_question
        self.related = related
        self.relation_type = relation_type
        self.prompts: list[str] = []

    async def generate(self, prompt, system_instruction=None, json_mode=False):
        self.prompts.append(prompt)
        if "PREGUNTA" in prompt:
            return json.dumps({"is_question": self.is_question})
        return json.dumps({
            "related": self.related, "relation_type": self.relation_type if self.related else None,
            "rationale": "coinciden en tema",
        })

    async def chat(self, messages, json_mode=False):
        return await self.generate(messages[-1]["content"] if messages else "")


def _event_for(data: dict, correlation_id=None) -> dict:
    return {"data": json.dumps(data), "correlation_id": str(correlation_id or new_id())}


def _wire_memory(monkeypatch):
    monkeypatch.setattr(memory_main, "embedding_provider", MockEmbedding(768))
    monkeypatch.setattr(memory_main, "event_bus", _NoopBus())
    monkeypatch.setattr(memory_main, "in_memory_db", InMemoryDatabase())
    monkeypatch.setattr(memory_main, "in_memory_vector_store", InMemoryVectorStore())
    monkeypatch.setattr(memory_main, "in_memory_thinking_graph", InMemoryThinkingGraph())


def _build_pipeline(monkeypatch, llm=None, agents_handler=None):
    """Cablea un pipeline real: memory_client contra la app real (ASGITransport, dedup/eventos
    reales incluidos); agents_client contra un MockTransport que solo registra la llamada."""
    _wire_memory(monkeypatch)
    memory_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=memory_main.app), base_url="http://memory")

    agents_calls = []

    def _default_handler(request: httpx.Request) -> httpx.Response:
        agents_calls.append(request)
        return httpx.Response(200, json={"correlation_id": str(new_id())})

    agents_client = httpx.AsyncClient(transport=httpx.MockTransport(agents_handler or _default_handler))

    pipeline = IngestionPipelineService(
        memory_client=memory_client, agents_client=agents_client,
        storage=InMemoryStorage(), ocr=MockOcr(), stt=MockStt(),
        llm=llm or _ScriptedLlm(),
        # MockEmbedding es un hash determinista por texto EXACTO, no semántico: la similitud
        # coseno entre dos textos DISTINTOS puede caer en cualquier punto de [-1, 1] (aquí,
        # medido: -0.45, negativo). -1.0 aísla de verdad "¿el veredicto del LLM se traduce en
        # una relación?" de "¿el embedding identifica bien que el par es afín?" (esto último
        # necesita Ollama real) — un 0.0 aparentemente "sin filtro" seguiría rechazando pares
        # con similitud negativa.
        similarity_threshold=-1.0,
    )
    return pipeline, agents_calls


@pytest.mark.asyncio
async def test_plain_text_message_is_ingested_with_provenance(monkeypatch):
    pipeline, _ = _build_pipeline(monkeypatch)

    event = _event_for({
        "message_id": "wamid.123", "sender_id": "5215512345678", "recipient_id": "mindos",
        "provider": "whatsapp", "text": "El puerto configurado es 443.", "media_url": None, "metadata": {},
    })
    await pipeline.handle_event(event)

    with TestClient(memory_main.app) as client:
        search = client.post("/api/v1/memory/search", params={"query": "puerto configurado"})
    assert search.status_code == 200
    results = search.json()["results"]
    assert any("443" in r["content"] for r in results)

    node = next(r for r in results if "443" in r["content"])
    provenance = TestClient(memory_main.app).get(f"/api/v1/memory/node/{node['node_id']}/provenance")
    assert provenance.status_code == 200
    source = provenance.json()["chain"][0]["source"]
    assert source["kind"] == "whatsapp"
    assert source["raw_ref"] == "wamid.123"


@pytest.mark.asyncio
async def test_cli_and_rest_messages_map_to_the_right_source_kind(monkeypatch):
    pipeline, _ = _build_pipeline(monkeypatch)

    await pipeline.handle_event(_event_for({
        "message_id": "cli-1", "sender_id": "cli-local", "recipient_id": "mindos",
        "provider": "cli", "text": "Nota capturada desde la terminal.", "media_url": None, "metadata": {},
    }))
    await pipeline.handle_event(_event_for({
        "message_id": "rest-1", "sender_id": "user-1", "recipient_id": "mindos",
        "provider": "rest", "text": "Nota capturada vía REST.", "media_url": None, "metadata": {},
    }))

    client = TestClient(memory_main.app)
    cli_search = client.post("/api/v1/memory/search", params={"query": "terminal"}).json()["results"]
    rest_search = client.post("/api/v1/memory/search", params={"query": "REST"}).json()["results"]

    cli_node = next(r for r in cli_search if "terminal" in r["content"])
    rest_node = next(r for r in rest_search if "REST" in r["content"])
    cli_prov = client.get(f"/api/v1/memory/node/{cli_node['node_id']}/provenance").json()
    rest_prov = client.get(f"/api/v1/memory/node/{rest_node['node_id']}/provenance").json()
    assert cli_prov["chain"][0]["source"]["kind"] == "cli"
    assert rest_prov["chain"][0]["source"]["kind"] == "api"


@pytest.mark.asyncio
async def test_image_message_is_stored_and_ocr_extracted_text_is_appended(monkeypatch):
    pipeline, _ = _build_pipeline(monkeypatch)
    media_bytes = b"contenido binario simulado de una imagen"

    await pipeline.handle_event(_event_for({
        "message_id": "wamid.img1", "sender_id": "5215512345678", "recipient_id": "mindos",
        "provider": "whatsapp", "text": "mira esto", "media_url": None,
        "metadata": {
            "media_kind": "image", "mimetype": "image/png",
            "media_base64": base64.b64encode(media_bytes).decode(),
        },
    }))

    with TestClient(memory_main.app) as client:
        search = client.post("/api/v1/memory/search", params={"query": "mira esto"})
    results = search.json()["results"]
    node = next(r for r in results if "mira esto" in r["content"])
    assert "Simulación OCR" in node["content"]  # MockOcr embebe este texto (ver mock_ocr.py)

    provenance = TestClient(memory_main.app).get(f"/api/v1/memory/node/{node['node_id']}/provenance")
    assert provenance.json()["chain"][0]["source"]["kind"] == "image"


@pytest.mark.asyncio
async def test_audio_message_is_stored_and_transcribed(monkeypatch):
    pipeline, _ = _build_pipeline(monkeypatch)
    media_bytes = b"audio simulado"

    await pipeline.handle_event(_event_for({
        "message_id": "wamid.audio1", "sender_id": "5215512345678", "recipient_id": "mindos",
        "provider": "whatsapp", "text": "", "media_url": None,
        "metadata": {
            "media_kind": "audio", "mimetype": "audio/ogg",
            "media_base64": base64.b64encode(media_bytes).decode(),
        },
    }))

    with TestClient(memory_main.app) as client:
        search = client.post("/api/v1/memory/search", params={"query": "Transcripción"})
    results = search.json()["results"]
    assert any("Simulación STT" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_message_with_no_resolvable_content_is_dropped_without_crashing(monkeypatch):
    """Un adjunto cuyo medio no se pudo descargar (F3-T4: comms_client falló) y sin texto ni
    caption no debe crear un nodo vacío ni lanzar excepciones."""
    pipeline, agents_calls = _build_pipeline(monkeypatch)

    await pipeline.handle_event(_event_for({
        "message_id": "wamid.empty", "sender_id": "5215512345678", "recipient_id": "mindos",
        "provider": "whatsapp", "text": "", "media_url": None, "metadata": {},
    }))

    assert agents_calls == []


@pytest.mark.asyncio
async def test_auto_link_creates_a_relation_when_llm_confirms_a_genuine_connection(monkeypatch):
    llm = _ScriptedLlm(related=True, relation_type="RELATED_TO")
    pipeline, _ = _build_pipeline(monkeypatch, llm=llm)

    await pipeline.handle_event(_event_for({
        "message_id": "m1", "sender_id": "u1", "recipient_id": "mindos", "provider": "rest",
        "text": "Idea: cachear las consultas frecuentes de reportes.", "media_url": None, "metadata": {},
    }))
    await pipeline.handle_event(_event_for({
        "message_id": "m2", "sender_id": "u1", "recipient_id": "mindos", "provider": "rest",
        "text": "Otra idea sobre cachear resultados de reportes.", "media_url": None, "metadata": {},
    }))

    with TestClient(memory_main.app) as client:
        search = client.post("/api/v1/memory/search", params={"query": "cachear reportes"})
        results = search.json()["results"]
        assert len(results) >= 2
        # El auto-enlazado corre al ingerir "m2" (aún no existe candidato al ingerir "m1"), y
        # crea la relación DESDE el nodo recién ingerido HACIA el existente — /neighbors solo
        # muestra salientes (query_relations_recursive), así que hay que mirar el nodo correcto.
        m2_node = next(r for r in results if "Otra idea" in r["content"])
        neighbors = client.get(f"/api/v1/memory/node/{m2_node['node_id']}/neighbors").json()["neighbors"]
    assert any(n["relation_type"] == "RELATED_TO" for n in neighbors)


@pytest.mark.asyncio
async def test_auto_link_creates_no_relation_when_llm_says_unrelated(monkeypatch):
    llm = _ScriptedLlm(related=False)
    pipeline, _ = _build_pipeline(monkeypatch, llm=llm)

    await pipeline.handle_event(_event_for({
        "message_id": "m1", "sender_id": "u1", "recipient_id": "mindos", "provider": "rest",
        "text": "Idea: cachear las consultas frecuentes de reportes.", "media_url": None, "metadata": {},
    }))
    await pipeline.handle_event(_event_for({
        "message_id": "m2", "sender_id": "u1", "recipient_id": "mindos", "provider": "rest",
        "text": "Otra idea sobre cachear resultados de reportes.", "media_url": None, "metadata": {},
    }))

    with TestClient(memory_main.app) as client:
        search = client.post("/api/v1/memory/search", params={"query": "cachear reportes"})
        node_id = search.json()["results"][0]["node_id"]
        neighbors = client.get(f"/api/v1/memory/node/{node_id}/neighbors").json()["neighbors"]
    assert neighbors == []


@pytest.mark.asyncio
async def test_question_dispatches_an_agent_with_reply_to_channel(monkeypatch):
    llm = _ScriptedLlm(is_question=True)
    pipeline, agents_calls = _build_pipeline(monkeypatch, llm=llm)

    await pipeline.handle_event(_event_for({
        "message_id": "wamid.q1", "sender_id": "5215512345678", "recipient_id": "mindos",
        "provider": "whatsapp", "text": "¿cuál es el puerto configurado?", "media_url": None, "metadata": {},
    }))

    assert len(agents_calls) == 1
    request = agents_calls[0]
    assert request.url.path == "/api/v1/agents/execute"
    params = dict(request.url.params)
    assert params["goal"] == "¿cuál es el puerto configurado?"
    assert params["reply_to_provider"] == "whatsapp"
    assert params["reply_to_sender_id"] == "5215512345678"


@pytest.mark.asyncio
async def test_question_from_cli_does_not_set_a_reply_to_channel(monkeypatch):
    """F3-T3: CLI no tiene un canal bidireccional al que responder de forma asíncrona."""
    llm = _ScriptedLlm(is_question=True)
    pipeline, agents_calls = _build_pipeline(monkeypatch, llm=llm)

    await pipeline.handle_event(_event_for({
        "message_id": "cli-q1", "sender_id": "cli-local", "recipient_id": "mindos",
        "provider": "cli", "text": "¿cuál es el puerto configurado?", "media_url": None, "metadata": {},
    }))

    params = dict(agents_calls[0].url.params)
    assert "reply_to_provider" not in params


@pytest.mark.asyncio
async def test_non_question_does_not_dispatch_an_agent(monkeypatch):
    llm = _ScriptedLlm(is_question=False)
    pipeline, agents_calls = _build_pipeline(monkeypatch, llm=llm)

    await pipeline.handle_event(_event_for({
        "message_id": "m1", "sender_id": "u1", "recipient_id": "mindos", "provider": "rest",
        "text": "El puerto configurado es 443.", "media_url": None, "metadata": {},
    }))

    assert agents_calls == []


@pytest.mark.asyncio
async def test_malformed_event_is_discarded_without_raising(monkeypatch):
    pipeline, agents_calls = _build_pipeline(monkeypatch)
    await pipeline.handle_event({"data": "esto no es JSON válido", "correlation_id": str(new_id())})
    assert agents_calls == []
