# Fase 3 — Gateway, autenticación y capa de comunicación

**Objetivo:** un **único punto de entrada seguro** y la capacidad de **capturar información desde
cualquier canal** (WhatsApp, CLI, REST, email), donde **todo termina en el mismo evento**
(`MessageReceivedEvent`) y pasa por un **pipeline de ingestión** unificado.

**Precondición:** Fase 1 (ingesta rica + provenance). Puede solaparse con Fase 2.
**Nivel:** épica + tareas clave + DoD. Refina al ejecutar.

---

## F3-T1 · Gateway (FastAPI) — entrada única

- Servicio nuevo en `gateway/` (hoy vacío): FastAPI con:
  - **Auth mono-usuario:** API key para servicios + JWT para el humano (login simple con
    contraseña hasheada Argon2; secreto en `.env`). Middleware que rechaza sin credencial.
  - **Originación de `correlation_id`** por request (header `X-Correlation-Id`).
  - **Rate-limit** (Redis) y **validación** de payloads (rechaza lo malformado antes de rutear).
  - **Routing/proxy** a Memory/Agents/Comms/MCP (por path `/api/v1/memory/*` → memory, etc.).
  - Endpoint `/health` agregado (estado de cada servicio downstream).
  - Endpoint de **aprobaciones**: `POST /api/v1/approvals/{id}/resolve` (resuelve los
    `pending_approval` de `F1-T8`).
- **DoD:** toda petición externa pasa por el Gateway autenticada; sin token → 401; con token →
  rutea y responde. `pending_approval` se puede aprobar/rechazar por el Gateway.

## F3-T2 · Traefik (TLS + routing en el server)

- Añade Traefik al compose de producción: TLS (Let's Encrypt si hay dominio, o cert autofirmado en
  LAN), enruta 443 → Gateway. El resto de servicios **no** se exponen fuera de `mindos-net`.
- **DoD:** el stack solo expone 443 (Traefik→Gateway); Memory/Agents/DB no son accesibles desde fuera.

## F3-T3 · Abstracción de comunicación (puertos) + canales CLI/REST

- En `schemas` ya existen `MessageReceivedEventData` / `MessageSentEventData`. Crea el servicio
  `comms/` con:
  - `CommunicationInboundPort` (recibe del canal) y `CommunicationOutboundPort` (envía al canal).
  - Adaptadores **CLI** (un comando `mindos capture "..."`) y **REST** (`POST /api/v1/comms/inbound`)
    que **emiten `MessageReceivedEvent`** al Event Bus. Idénticos en salida sin importar el origen.
- **DoD:** capturar por CLI y por REST produce el **mismo** evento en el stream; un test lo verifica.

## F3-T4 · Adaptador WhatsApp

- Microservicio Node con **Baileys** (no oficial, sin costo) **o** Meta **Cloud API** (oficial, requiere
  número/registro). Recomendado empezar con Baileys para privacidad/costo; dejar Cloud API como opción.
  - Traduce mensajes entrantes (texto, imagen, audio, PDF) → `MessageReceivedEvent` (con `media_url`
    apuntando al blob ya subido al Storage, o adjunto para que el pipeline lo baje).
  - Consume `MessageSentEvent` para responder al usuario.
- Aísla credenciales/sesión de WhatsApp en volumen persistente; nunca en el repo.
- **DoD:** enviar un WhatsApp al bot genera un `MessageReceivedEvent` y, tras procesarlo, el usuario
  recibe respuesta por el mismo canal.

## F3-T5 · Pipeline de ingestión (consumidor de eventos)

- Servicio/consumidor que se suscribe a `mindos.comms` (grupo de consumo) y por cada
  `MessageReceivedEvent`:
  1. Determina tipo (texto/imagen/pdf/audio).
  2. Si es binario: lo guarda en **Storage** (crea `source`), extrae texto con **OCR/STT**.
  3. Genera embedding, aplica **dedup** (F1-T5), crea el objeto cognitivo con **provenance** (F1-T2).
  4. Enlaza automáticamente (relaciones por similitud/entidades; usa `qwen2.5-coder:14b` para extraer
     entidades y proponer relaciones).
  5. Emite `com.mindos.memory.knowledge.created`.
  6. Opcional: dispara un agente (Fase 2) si el mensaje es una **pregunta** (clasificación por LLM).
- **DoD:** mandar por WhatsApp un PDF resulta en: blob en Storage + `source` + nodo indexado +
  relaciones + evento; y si era pregunta, una respuesta generada.

## F3-T6 · Adaptadores reales OCR / STT / Storage

- **OCR:** `TesseractOcr` (impl. de `OcrPort`) vía `pytesseract`/servicio; PDFs con `pypdf`+OCR fallback.
- **STT:** `FasterWhisperStt` (nuevo `SttPort`) para audio → texto (modelo `small`/`base` local).
- **Storage:** `MinioStorage` o `LocalFsStorage` (impl. de `StoragePort`), URIs estables, no borrado duro.
- **DoD:** cada adaptador tiene test (con archivo de muestra) y está detrás de su puerto; el pipeline
  los usa por inyección.

## F3-T7 · Mensajería saliente + resolución de aprobaciones

- El agente/Memory emite `MessageSentEvent`; el adaptador del canal correspondiente lo entrega.
- Las capacidades `requires_approval` notifican al usuario por su canal y esperan la resolución
  (Gateway `F3-T1` / Dashboard `F4`).
- **DoD:** una acción sensible pregunta al usuario por WhatsApp/Dashboard y solo procede tras el "sí".

---

## Cierre de Fase 3
- [ ] F3-T1 Gateway · [ ] F3-T2 Traefik · [ ] F3-T3 comms CLI/REST · [ ] F3-T4 WhatsApp
- [ ] F3-T5 pipeline · [ ] F3-T6 OCR/STT/Storage · [ ] F3-T7 salida+aprobaciones

**Hito:** MindOS ya **captura desde el mundo real** y responde por el mismo canal, con todo lo
capturado convertido en conocimiento indexado, enlazado y trazable.
