import base64
import json
from typing import Any
from uuid import UUID

import httpx
from mindos_common.logging import get_logger
from mindos_schemas.domain.source import SourceKind
from mindos_schemas.events.v1.communication_events import MessageReceivedEventData

from memory.src.application.ports.llm import LlmPort
from memory.src.application.ports.ocr import OcrPort
from memory.src.application.ports.storage import StoragePort
from memory.src.application.ports.stt import SttPort

logger = get_logger("ingestion_pipeline")

# Subconjunto de RelationType apropiado para auto-enlazado por similitud (F3-T5, paso 4):
# excluye tipos que ya tienen su propio mecanismo dedicado (CONTRADICTS→F2-T5,
# DUPLICATE_OF→F1-T5, EVIDENCES/DECIDES/ANSWERS→Thinking Graph/Fase 2).
AUTO_LINK_RELATION_TYPES = {"RELATED_TO", "PART_OF", "MENTIONS", "CAUSED_BY", "DERIVED_FROM", "LEADS_TO"}
# Mismo calibre que F2-T5 (F2-T5 NOTAS: no relacionados ~0.5, mismo tema ~0.77-0.90).
AUTO_LINK_SIMILARITY_THRESHOLD = 0.65
AUTO_LINK_TOP_K = 3


def _determine_source_kind(provider: str, media_kind: str | None, mimetype: str | None) -> SourceKind:
    if provider == "cli":
        return SourceKind.CLI
    if provider == "whatsapp":
        if media_kind == "image":
            return SourceKind.IMAGE
        if media_kind == "audio":
            return SourceKind.AUDIO
        if media_kind == "document" and mimetype == "application/pdf":
            return SourceKind.PDF
        return SourceKind.WHATSAPP
    return SourceKind.API  # 'rest' y cualquier provider futuro no listado


class IngestionPipelineService:
    """
    F3-T5: consumidor de `mindos.comms` — por cada `MessageReceivedEvent` (CLI, REST o
    WhatsApp, F3-T3/T4), determina el tipo de contenido, resuelve binarios (Storage + OCR/STT,
    F3-T6), ingiere el objeto cognitivo con provenance (reusando `POST /memory/ingest`, que ya
    aplica dedup F1-T5 y emite `com.mindos.memory.knowledge.created`), propone relaciones por
    similitud (paso 4, simplificado) y opcionalmente dispara un agente si es una pregunta.

    Dos clientes HTTP distintos, cada uno con su `base_url` ya fijado:
    - `memory_client`: hacia el propio Memory Service. En producción, loopback real
      (`http://localhost:8001`, mismo proceso/contenedor); en tests, `httpx.ASGITransport`
      apuntando a la misma app. Reutiliza ingest/relación/búsqueda tal cual en vez de
      reimplementar dedup/versión/eventos/sesión de DB aquí — ningún acceso directo a
      `DatabasePort`/`VectorStorePort` (son request-scoped vía `Depends`, no aptos para un
      consumidor de fondo de vida larga).
    - `agents_client`: hacia el Agents Service (otro proceso/contenedor), red real.
    """
    def __init__(
        self,
        memory_client: httpx.AsyncClient,
        agents_client: httpx.AsyncClient,
        storage: StoragePort,
        ocr: OcrPort,
        stt: SttPort,
        llm: LlmPort,
        similarity_threshold: float = AUTO_LINK_SIMILARITY_THRESHOLD,
    ):
        self.memory_client = memory_client
        self.agents_client = agents_client
        self.storage = storage
        self.ocr = ocr
        self.stt = stt
        self.llm = llm
        # Configurable (no una constante fija): igual que F2-T5, aislar "¿el veredicto del LLM
        # se traduce bien en una relación?" de "¿el embedding produce una similitud realista?"
        # requiere poder bajarlo a 0 en tests con embeddings de prueba no-semánticos.
        self.similarity_threshold = similarity_threshold

    async def handle_event(self, event: dict[str, Any]) -> None:
        """Callback del consumidor del Event Bus (`RedisEventBus.subscribe`)."""
        try:
            data = MessageReceivedEventData.model_validate_json(event["data"])
        except Exception as e:
            logger.error("Evento MessageReceivedEvent malformado, se descarta", error=str(e))
            return

        correlation_id = event.get("correlation_id")
        content_text, source_uri, source_kind = await self._resolve_content(data)
        if not content_text.strip():
            logger.info(
                "Mensaje sin contenido capturable tras resolver medios, se descarta",
                message_id=data.message_id, provider=data.provider,
            )
            return

        node_id = await self._ingest(data, content_text, source_uri, source_kind, correlation_id)
        if node_id is None:
            return

        await self._auto_link(node_id, content_text)
        await self._maybe_dispatch_agent(data, content_text, correlation_id)

    async def _resolve_content(
        self, data: MessageReceivedEventData
    ) -> tuple[str, str | None, SourceKind]:
        """Pasos 1-2: determina el tipo de contenido; si hay binario adjunto (F3-T4 lo manda
        en `metadata.media_base64`), lo guarda en Storage y extrae texto con OCR/STT."""
        media_kind = data.metadata.get("media_kind")
        mimetype = data.metadata.get("mimetype")
        source_kind = _determine_source_kind(data.provider, media_kind, mimetype)

        media_b64 = data.metadata.get("media_base64")
        if not media_kind or not media_b64:
            return data.text, None, source_kind

        file_bytes = base64.b64decode(media_b64)
        source_uri = await self.storage.save(data.message_id, file_bytes)

        extracted = ""
        try:
            if media_kind == "image" or (media_kind == "document" and mimetype == "application/pdf"):
                extracted = await self.ocr.extract_text(file_bytes, mimetype or "application/octet-stream")
            elif media_kind == "audio":
                extracted = await self.stt.transcribe(file_bytes, mimetype or "audio/ogg")
        except Exception as e:
            logger.error("Fallo extrayendo texto del medio adjunto", error=str(e), media_kind=media_kind)

        combined_text = "\n".join(part for part in [data.text, extracted] if part).strip()
        return combined_text, source_uri, source_kind

    async def _ingest(
        self,
        data: MessageReceivedEventData,
        content_text: str,
        source_uri: str | None,
        source_kind: SourceKind,
        correlation_id: str | None,
    ) -> UUID | None:
        """Paso 3: ingesta real (dedup F1-T5 + provenance F1-T2 + evento, todo vía el endpoint
        existente) — best-effort: un fallo aquí se registra pero no tumba el consumidor."""
        payload = {
            "object_type": "note",
            "title": content_text[:80] or f"Captura de {data.provider}",
            "content": content_text,
            "author": data.sender_id,
            "metadata": {"provider": data.provider, "message_id": data.message_id},
            "source": {
                "kind": source_kind.value, "uri": source_uri or f"{data.provider}:{data.message_id}",
                "raw_ref": data.message_id, "metadata": data.metadata,
            },
        }
        headers = {"X-Correlation-Id": str(correlation_id)} if correlation_id else {}
        try:
            resp = await self.memory_client.post("/api/v1/memory/ingest", json=payload, headers=headers)
            resp.raise_for_status()
            return UUID(resp.json()["node_id"])
        except Exception as e:
            logger.error("Fallo ingiriendo el mensaje capturado", error=str(e), message_id=data.message_id)
            return None

    async def _auto_link(self, node_id: UUID, content_text: str) -> None:
        """
        Paso 4 (simplificado): en vez de extracción de entidades completa, reusa el patrón de
        F2-T5 (similitud + confirmación LLM) para proponer relaciones tipadas genéricas — misma
        doble puerta contra falsos positivos, con un catálogo de tipos distinto. Los candidatos
        salen de `/memory/search` (ya trae `content` + `score`), no de acceso directo al store.
        """
        try:
            search_resp = await self.memory_client.post(
                "/api/v1/memory/search", params={"query": content_text, "limit": AUTO_LINK_TOP_K + 1},
            )
            search_resp.raise_for_status()
            candidates = search_resp.json()["results"]
        except Exception as e:
            logger.warning("No se pudo buscar candidatos para auto-enlazado", error=str(e))
            return

        for candidate in candidates:
            candidate_id = candidate["node_id"]
            if candidate_id == str(node_id) or candidate["score"] < self.similarity_threshold:
                continue

            verdict = await self._ask_llm_for_relation(content_text, candidate["content"])
            if not verdict:
                continue

            try:
                rel_resp = await self.memory_client.post("/api/v1/memory/relation", json={
                    "source_id": str(node_id), "target_id": candidate_id,
                    "relation_type": verdict["relation_type"],
                })
                rel_resp.raise_for_status()
            except Exception as e:
                logger.warning("No se pudo crear la relación auto-enlazada", error=str(e))

    async def _ask_llm_for_relation(self, content_a: str, content_b: str) -> dict[str, Any] | None:
        prompt = (
            "Actúa como un sistema de enlazado automático de una base de conocimiento personal.\n\n"
            f"Contenido nuevo: {content_a}\n\nContenido existente: {content_b}\n\n"
            "¿Existe una relación de conocimiento genuina entre ambos (no una coincidencia "
            "superficial de palabras)? Si sí, clasifícala con UNA de estas etiquetas EXACTAS: "
            f"{', '.join(sorted(AUTO_LINK_RELATION_TYPES))}.\n\n"
            'Responde OBLIGATORIAMENTE en JSON: {"related": true o false, '
            '"relation_type": "UNA_ETIQUETA_O_null", "rationale": "explicación breve"}'
        )
        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            data = json.loads(response_text)
            if not data.get("related"):
                return None
            relation_type = data.get("relation_type")
            if relation_type not in AUTO_LINK_RELATION_TYPES:
                return None
            return {"relation_type": relation_type, "rationale": data.get("rationale", "")}
        except Exception as e:
            logger.warning("Fallo evaluando auto-enlazado con el LLM; se descarta el candidato", error=str(e))
            return None

    async def _maybe_dispatch_agent(
        self, data: MessageReceivedEventData, content_text: str, correlation_id: str | None
    ) -> None:
        """Paso 6: si el mensaje es una pregunta (clasificación LLM), dispara un agente que
        la responda. `reply_to` (F3-T7) permite notificar por el mismo canal si una capacidad
        queda pendiente de aprobación a mitad del razonamiento."""
        if not await self._classify_is_question(content_text):
            return

        params: dict[str, str] = {"goal": content_text}
        if correlation_id:
            params["correlation_id"] = str(correlation_id)
        if data.provider != "cli":  # CLI no tiene un canal bidireccional al que responder (F3-T3)
            params["reply_to_provider"] = data.provider
            params["reply_to_sender_id"] = data.sender_id

        try:
            resp = await self.agents_client.post("/api/v1/agents/execute", params=params)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("No se pudo disparar el agente para la pregunta detectada", error=str(e))

    async def _classify_is_question(self, text: str) -> bool:
        prompt = (
            "¿El siguiente mensaje es una PREGUNTA que espera una respuesta, o es una "
            "afirmación/nota/captura de información?\n\n"
            f"Mensaje: {text}\n\n"
            'Responde OBLIGATORIAMENTE en JSON: {"is_question": true o false}'
        )
        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            return bool(json.loads(response_text).get("is_question", False))
        except Exception as e:
            logger.warning("Fallo clasificando si el mensaje es una pregunta; se asume que no", error=str(e))
            return False
