# MindOS — Plan de ejecución a producción

> **Audiencia:** quien ejecute este plan, tarea por tarea.
> **Meta:** llevar MindOS desde el kernel actual (~10%) hasta un KOS funcional, fiel a la
> visión, y **desplegado en producción** en el servidor Ubuntu 24/7.
> **Fecha base:** 2026-07-21.

Este directorio es la **fuente de verdad** de ejecución. Léelo completo antes de empezar.
Cada fase vive en su propio archivo y se ejecuta **en orden**. No saltes fases.

---

## 0. Reglas de ejecución (globales — OBLIGATORIAS)

1. **Una tarea a la vez, en orden.** Cada tarea tiene un ID (`F0-T1`), objetivo, archivos,
   pasos y **Criterio de Aceptación (DoD)**. No pases a la siguiente hasta que el DoD esté verde.
2. **Verifica siempre.** Cada tarea termina con un comando concreto (`pytest`, `curl`, `ruff`)
   cuyo resultado debe cumplir el DoD. Si no pasa, corrige antes de avanzar.
3. **Commit por tarea.** Mensaje convencional: `feat(memory): F1-T3 modelo cognitivo rico`.
   Un commit atómico por tarea facilita revisión y rollback.
4. **TDD cuando sea posible.** Escribe o ajusta el test primero; luego haz que pase.
5. **Respeta la hexagonal.** `domain/` y `application/` NUNCA importan `infrastructure/`.
   Toda dependencia externa entra por un **puerto** (ABC) y sale por un **adaptador**.
6. **Nunca borrado duro de conocimiento.** Todo es soft-delete/tombstone o versión. Es un
   principio del producto, no una preferencia.
7. **IDs siempre `uuid.uuid7()`** (disponible en Python 3.12+/3.14). Prohibido `hash()` para IDs.
8. **No inventes contratos.** Los DTOs/eventos viven en `schemas/`. Si necesitas uno nuevo,
   créalo ahí y reutilízalo; no dupliques modelos.
9. **Marca progreso.** Al terminar una tarea, marca su casilla `[x]` en el archivo de la fase.
10. **Si algo del plan choca con la realidad del código, PARA y anótalo** en `plan/NOTAS.md`
    con la discrepancia y tu decisión; no improvises silenciosamente.

---

## 1. Decisiones de arquitectura ya tomadas (no volver a debatir)

| Área | Decisión | Motivo |
|---|---|---|
| Estructura repo | **Monorepo** (raíz = un solo git). Se eliminan los `.git` anidados vacíos. | Los submódulos no tienen commits; el monorepo simplifica build/test/deploy. Tarea `F0-T1`. |
| Lenguaje servicios | Python **3.12+** (funciona en 3.14 de la máquina). | Mejor soporte de libs; `uuid7` disponible. |
| Web framework | **FastAPI + Uvicorn**. | Ya en uso. |
| Persistencia | **PostgreSQL 16 + pgvector**. | Ya elegido; vector + relacional + CTE recursivas en un solo motor. |
| Grafo | **Relacional (tablas + CTE recursivas)**, no Neo4j. | Mantiene "local, bajo costo". Apache AGE queda como upgrade opcional futuro. |
| Migraciones | **Alembic**. | Hoy no existen → Postgres no arranca. |
| ORM | **SQLAlchemy 2.0 async**. | Ya en uso. |
| Bus de eventos | **Redis Streams** (ya implementado en `common`). | Consumer groups + correlación. |
| Cache/locks | **Redis**. | Ya presente. |
| LLM | **Claude Sonnet 5.5** vía API para el asistente y el razonamiento; **Ollama** solo para embeddings (y como alternativa 100 % local con `LLM_PROVIDER=ollama`). | Cambiado en la Fase 7: ver [`08-asistente-personal-claude.md`](08-asistente-personal-claude.md) para el motivo y el costo de privacidad que se acepta. |
| Embeddings | **nomic-embed-text (768 dim)** vía Ollama. | Descargado y verificado. `bge-m3` (1024, multilingüe) = upgrade opcional. |
| Agentes | **LangGraph**. | Ya en uso. |
| Gateway | Servicio **FastAPI** (BFF + auth) detrás de **Traefik** (TLS/routing en el server). | Punto de entrada único de la visión. |
| Comunicación | **CLI + REST primero**; WhatsApp vía microservicio Node **Baileys** (o Meta Cloud API). | Todo emite el mismo `MessageReceivedEvent`. |
| OCR / STT / Storage | **Tesseract** (OCR), **faster-whisper** (audio), **MinIO/FS local** (blobs). | Locales, detrás de puertos. |
| Dashboard | **Next.js (React) + Cytoscape.js**. | Grafo, timeline, trazas. |
| MCP | **Python MCP SDK** (servidor stdio + HTTP). | Exponer capacidades a asistentes externos. |
| Mobile | **PWA instalable** primero; React Native después. | Captura rápida con mínimo esfuerzo. |
| Observabilidad | structlog + **OpenTelemetry** (traces) + **Prometheus/Grafana** (métricas). | Ya hay logging con correlación. |
| CI | **GitHub Actions** (ruff + pytest + build de imágenes). | Calidad continua. |
| Auth | **Mono-usuario**: API key + JWT en el Gateway. Multi-usuario = futuro. | Simplicidad para v1. |

---

## 2. Asignación definitiva de modelos (Ollama)

Verificado en la máquina el 2026-07-21. Configúralo en `mindos_common` (ver `F0-T5`) para que
**cada rol apunte a un modelo por variable de entorno**, con override por host (server vs workstation).

| Rol cognitivo | Modelo por defecto | Alternativa / notas |
|---|---|---|
| **Embeddings** | `nomic-embed-text` (768 dim) | `bge-m3` (1024, mejor en español) si se prioriza calidad multilingüe. |
| **Planner / Reviewer / razonamiento** (server 24/7) | `qwen3:8b` | Modo *thinking* + JSON; entra en 16 GB junto a Postgres/Redis. |
| **Extracción / clasificación / tipado de entidades** (JSON estricto) | `qwen2.5-coder:14b` (workstation) o `qwen3:8b` (server) | Salida estructurada muy fiable. |
| **Investigación / síntesis pesada** (workstation, on-demand) | `qwen3-coder:30b` (MoE 30B-A3B) | No cargar en el server 16 GB; usar solo en la estación. |
| **Fallback general** | `llama3:latest` | Último recurso. |

**Restricción de hardware:** el server (i7-1065G7, 16 GB, sin GPU dedicada) corre 24/7 Postgres +
Redis + servicios + Ollama. Presupuesto realista de LLM en el server: **un modelo ~8B Q4 (~5-6 GB) cargado**.
Los modelos ≥14B se ejecutan bajo demanda en la **workstation** (Ryzen 9 8940HX). El `LlmPort` debe
permitir enrutar por rol a distintas `OLLAMA_URL` (server local vs workstation por LAN).

Variables de entorno canónicas (definir en `.env` y en `mindos_common.config`):
```
OLLAMA_URL_LOCAL=http://localhost:11434        # server / mismo host
OLLAMA_URL_WORKSTATION=http://192.168.x.y:11434 # estación por LAN (opcional)
LLM_MODEL_REASONING=qwen3:8b
LLM_MODEL_EXTRACTION=qwen2.5-coder:14b
LLM_MODEL_RESEARCH=qwen3-coder:30b
LLM_MODEL_FALLBACK=llama3:latest
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIM=768
```

---

## 3. Arquitectura objetivo (producción)

```
                    Internet / LAN
                          │
                     [ Traefik ]  TLS, routing, rate-limit
                          │
                   [ Gateway (FastAPI) ]  auth (JWT/API key), validación, correlation-id
                          │
        ┌─────────────┬───┴────┬──────────────┬───────────────┐
        │             │        │              │               │
   [ Memory ]   [ Agents ]  [ Comms ]     [ MCP ]        [ Dashboard ]
   knowledge+   planner/    whatsapp/cli/  tools a         Next.js
   thinking     executor/   email +        asistentes
   graph, RAG   reviewer    ingest. pipe   externos
        │             │        │
        └──────┬──────┴────────┘
               │  (todos publican/consumen)
        [ Redis Streams  ·  Event Bus ]
               │
        [ PostgreSQL 16 + pgvector ]   [ MinIO / FS ]   [ Ollama ]
        knowledge, versions, relations,   blobs           LLM+embeddings
        thinking graph, event_log
```

Regla de oro: **nada accede a la infraestructura directamente**; todo pasa por el Kernel
(Memory/Agents) y sus puertos. El Gateway es el único ingreso externo.

---

## 4. Índice de fases y dependencias

> **▶ Para EJECUTAR, empieza por [`07-runway-a-produccion.md`](07-runway-a-produccion.md):** es la
> secuencia maestra ordenada (stages + puertas de despliegue + protocolo de ejecución) que lleva de
> aquí a producción. Los archivos de fase de abajo tienen el detalle de cada tarea; el runway tiene
> el orden y los gates.

| Fase | Archivo | Entrega | Estado / Depende de |
|---|---|---|---|
| **0 · Fundaciones** | [`00-fundaciones.md`](00-fundaciones.md) | Kernel correcto, persistente, event-driven, arrancable con Docker. | ✅ código hecho (falta verificación online) |
| **1 · Knowledge Core** | [`01-knowledge-core.md`](01-knowledge-core.md) | Modelo cognitivo rico, consulta temporal, GraphRAG, executor real. | ✅ código hecho (falta verificación online) |
| **2 · Thinking Graph** | [`02-thinking-graph.md`](02-thinking-graph.md) | Explicabilidad, trazas de razonamiento, Cognitive Query API, contradicciones. | ⏳ depende de 1 |
| **3 · Gateway + Comunicación** | [`03-gateway-comunicacion.md`](03-gateway-comunicacion.md) | Entrada única + auth; captura WhatsApp/CLI/email; pipeline de ingestión. | ⏳ depende de 1 |
| **4 · Interfaces** | [`04-interfaces.md`](04-interfaces.md) | Dashboard (grafo/timeline/trazas), servidor MCP, PWA de captura. | ⏳ depende de 2, 3 |
| **5 · Automatización** | [`05-automatizacion.md`](05-automatizacion.md) | Reflexión/consolidación, resurfacing, investigación, lifecycle. | ⏳ depende de 2 |
| **6 · Producción y despliegue** | [`06-produccion-despliegue.md`](06-produccion-despliegue.md) | Hardening, Docker stack completo, deploy al server, backups, observabilidad, CI/CD. | ⏳ incremental (0→5) |
| **7 · Asistente personal (Claude)** | [`08-asistente-personal-claude.md`](08-asistente-personal-claude.md) | Asistente conversacional sobre Claude Sonnet 5.5, streaming por el Gateway, vista Asistente y sistema visual. | 🟡 F7-T1..T6 hechas; falta verificación con API key real (F7-T7) |
| **8 · Agente y consola** | [`09-agente-y-consola.md`](09-agente-y-consola.md) | Qué distingue a MindOS, investigación web y rutinas del agente, portada con estadísticas, catálogo de diagramas, sistema visual nuevo. | 🟡 código hecho; falta verificación con API key real (F8-T10) |
| **▶ Runway de ejecución** | [`07-runway-a-produccion.md`](07-runway-a-produccion.md) | Secuencia maestra: stages + puertas de despliegue + protocolo de ejecución. | **empieza aquí** |

> **Nivel de detalle:** las fases 0-2 están a nivel de tarea atómica (near-term, máxima precisión).
> Las fases 3-5 están a nivel de épica + tareas clave + DoD (dependen de resultados previos; se
> refinan al llegar). La fase 6 es un playbook de despliegue aplicable de forma incremental —
> empieza a usar sus secciones de Docker/CI desde la Fase 0.

---

## 5. Definición de "listo para producción" (checklist de salida)

MindOS se considera **en producción** cuando:

- [ ] `docker compose up` en el server levanta todo el stack sano (healthchecks verdes).
- [ ] Ingesta real (texto, PDF, imagen, audio, WhatsApp) → indexado + enlazado + evento emitido.
- [ ] Búsqueda semántica + GraphRAG con embeddings reales y citas.
- [ ] Las 7 preguntas insignia responden vía API y Dashboard.
- [ ] `/explain` reconstruye el razonamiento desde el Thinking Graph.
- [ ] Detección de contradicciones activa; agente de consolidación corriendo en schedule.
- [ ] Gateway con auth; Traefik con TLS; nada expuesto sin autenticar.
- [ ] Backups automáticos de Postgres + blobs; restore probado.
- [ ] Observabilidad: dashboards de métricas + trazas + logs con correlación.
- [ ] CI verde (ruff + pytest) en cada push; imágenes construidas.
- [ ] Migraciones Alembic versionadas; arranque en limpio reproducible.
- [ ] Documentado: `README` de operación (arrancar, respaldar, restaurar, actualizar).

Cuando todas estén marcadas, ejecuta el smoke-test end-to-end de `06-produccion-despliegue.md §Smoke`.
