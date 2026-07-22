# Fase 4 — Interfaces: Dashboard, MCP y Mobile

**Objetivo:** ver, navegar y **exponer** el conocimiento. El Dashboard hace tangible el KOS; el
servidor MCP convierte a MindOS en la **memoria de largo plazo de asistentes externos** (Claude incl.).

**Precondición:** Fases 2 y 3. **Nivel:** épica + tareas clave + DoD.

---

## F4-T1 · Dashboard (Next.js + Cytoscape.js)

Servicio `dashboard/` (hoy vacío). App Next.js (React) que consume **solo el Gateway** (con JWT).
Vistas mínimas de v1:
1. **Búsqueda + resultados con citas** (usa `/context` y `/search`), mostrando `source` y score.
2. **Grafo de conocimiento** interactivo (Cytoscape.js): nodos por `object_type` (color), aristas
   tipadas; click en nodo → panel con versiones, provenance, vecinos.
3. **Timeline**: línea temporal de captura/versiones; slider de **"as-of"** que llama a `/timetravel`.
4. **Visor de razonamiento**: dado un nodo o episodio, renderiza `/explain` (árbol Pregunta→…→Aprendizaje).
5. **Panel de las 7 preguntas**: cada una como widget que llama a su endpoint `/cognitive/*`.
6. **Bandeja de contradicciones** y **de aprobaciones** (resolver `pending_approval`).
7. **Captura rápida** (textarea + subida de archivo) → `/comms/inbound`.

**DoD:** desde el navegador, autenticado, se puede capturar, buscar con citas, explorar el grafo,
viajar en el tiempo, ver una explicación de razonamiento y responder las 7 preguntas.

## F4-T2 · Servidor MCP

Servicio `mcp/` (hoy vacío) con el **Python MCP SDK**. Expone como **tools MCP**:
- `mindos_search(query)` → búsqueda + citas.
- `mindos_ingest(title, content, object_type, source)` → captura.
- `mindos_context(query)` → GraphRAG bundle.
- `mindos_ask_cognitive(question_type, params)` → las 7 preguntas.
- `mindos_explain(node_id)` → traza de razonamiento.
Transportes: **stdio** (para clientes locales tipo Claude Desktop/Code) y **HTTP** (para remoto,
detrás del Gateway). Autenticación por API key.

**DoD:** un cliente MCP (p.ej. Claude Code) configura el server y puede buscar/ingerir/explicar en
MindOS; documenta el `mcp.json` de ejemplo.

## F4-T3 · Mobile (PWA de captura)

- PWA instalable (puede ser parte del Dashboard con manifest + service worker): captura rápida de
  texto/foto/audio, share-target (compartir a MindOS desde otras apps), funciona offline-first con
  cola que sincroniza al Gateway.
- **DoD:** desde el móvil se instala la PWA, se captura una nota/foto sin conexión y se sincroniza al
  recuperar red.

---

## Cierre de Fase 4
- [x] F4-T1 Dashboard · [x] F4-T2 MCP · [x] F4-T3 PWA

**Hito:** MindOS es usable por un humano (Dashboard/móvil) y por máquinas (MCP).

---

✅ **Fase 4 completa (2026-07-22).** 161/162 tests Python no-integration + `ruff check .` limpio
(el único fallo, `test_faster_whisper_stt.py` en Windows, es pre-existente de F3-T6 y no tiene
relación con esta fase — ver `plan/NOTAS.md`). Dashboard (`dashboard/`, nuevo, Next.js 16 +
Cytoscape.js) y servidor MCP (`mcp_server/`, F4-T2, sesión previa) completos; PWA de captura
(manifest + service worker + share_target + cola offline) añadida sobre el Dashboard existente.

A diferencia de las fases anteriores (verificadas principalmente con pytest), el cierre de esta
fase se apoyó sobre todo en **verificación real en navegador**: sin Docker en este entorno, se
levantaron Memory/Agents/Comms/Gateway directo con `uvicorn` en el host (sus defaults ya apuntan
a `localhost:800x`, pensados para esto) con Ollama real (no mocks) sirviendo embeddings/LLM, se
sembraron datos de conocimiento reales, y se navegaron las 8 vistas del Dashboard más el flujo de
la PWA con el Browser tool, autenticado de verdad contra el Gateway. Esa disciplina — probar el
camino real en vez de confiar solo en tests aislados — encontró **cuatro bugs reales** nunca antes
ejercitados por un cliente externo, documentados en detalle en `plan/NOTAS.md`:
1. `/api/v1/memory/node/{id}/neighbors` solo seguía aristas salientes (un nodo `decision` con solo
   evidencia entrante se veía aislado en el Grafo) — corregido combinando `query_relations_recursive`
   con `query_incoming_relations`, con dedup para el caso de ciclos.
2. El Gateway nunca aprendió a rutear `thinking`/`cognitive` (montados en Memory bajo su propio
   prefijo, igual que `approvals` en Agents) — el Visor de razonamiento y el Panel de las 7
   preguntas devolvían 404 la primera vez que se probaron a través del Gateway real.
3. El slider "as-of" de Timeline excluía la última versión por la diferencia de precisión entre
   microsegundos (backend) y milisegundos (`Date` de JS).
4. Una condición de carrera de React Strict Mode en la recolección de datos de `share_target`
   (el efecto que consume la cache se ejecuta dos veces en dev) — corregida con un guard de `useRef`.

También cerró un gap real de API que ninguna fase anterior necesitó: no existía forma de listar
aprobaciones pendientes (`ApprovalPort` solo tenía `get`/`resolve`), haciendo imposible una
"bandeja" de aprobaciones — se agregó `list_pending()` + `GET /api/v1/approvals/`.

**Pendiente (no bloqueante, mismo patrón que Fases 0-3):** verificación *online* completa del
stack en un server real (Fase 6 §1-§2); instalar la PWA de verdad y disparar "Compartir..." desde
el selector nativo del sistema operativo son gestos de UI del propio SO que ninguna herramienta de
automatización de navegador disponible aquí puede accionar; la entrega final de una captura exitosa
(Dashboard o PWA) no verificable sin Redis real (misma limitación que Stage 3, la Captura llega
hasta el Comms real y recibe su 503 genuino); observabilidad (`06 §7`, Prometheus/Grafana) no
ejecutada — es una adición recomendada para este stage, no parte de `F4-T1..T3`. Ver Stage 4 en
`plan/07-runway-a-produccion.md`.
