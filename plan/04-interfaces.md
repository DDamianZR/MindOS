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
