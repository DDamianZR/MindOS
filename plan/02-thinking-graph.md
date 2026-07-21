# Fase 2 — Thinking Graph y explicabilidad (el diferenciador)

**Objetivo:** que MindOS **explique cómo piensa**, no solo qué responde. Capturar procesos de
razonamiento (Pregunta→Hipótesis→Evidencia→Decisión→Resultado→Aprendizaje), persistir las trazas
de los agentes, responder las **7 preguntas insignia** y **detectar contradicciones**.

**Precondición:** Fase 1 cerrada. Esto es lo que convierte MindOS en un KOS y no en "otra app de notas".

---

## F2-T1 · Modelo del Thinking Graph

**Diseño:** reutiliza el objeto cognitivo (Fase 1) para los **nodos de pensamiento**
(`object_type` ∈ {`question, hypothesis, investigation, evidence, decision, outcome, learning`}) y
usa `relations` tipadas (`ANSWERS, EVIDENCES, SUPPORTS, CONTRADICTS, DECIDES, LEADS_TO, DERIVED_FROM`)
para conectar razonamiento con conocimiento. Añade además una capa de **episodios**:

**Pasos:**
1. Tablas nuevas (`memory/.../models.py` + migración):
   - `reasoning_episodes` (`id`, `goal`, `correlation_id`, `started_at`, `ended_at`, `status`,
     `final_output`, `agent`).
   - `reasoning_steps` (`id`, `episode_id`, `step_index`, `kind` = `plan|execute|review|replan`,
     `input`, `output`, `capability_name`, `approved`, `feedback`, `created_at`,
     `knowledge_refs JSONB` = node_ids citados/creados).
2. Puerto `ThinkingGraphPort` + adaptadores Pg/InMemory: `create_episode`, `append_step`,
   `close_episode`, `get_episode`, `get_episodes_by_node`, `walk_reasoning(node_id)`.
3. DTOs en `schemas/api/v1/thinking_dto.py`.

**DoD:** se puede crear un episodio, añadirle pasos y recuperarlo completo por id y por `node_id` citado.

---

## F2-T2 · Persistir la traza de razonamiento de los agentes

**Por qué:** cada corrida Planner→Executor→Reviewer debe quedar registrada y ser re-consultable.

**Pasos:**
1. En `agent_graph.py`: al iniciar `_plan_node`, crea un `reasoning_episode` (si no existe) usando
   el `correlation_id`. En cada nodo (`plan/execute/review/replan`) añade un `reasoning_step` con
   input/output y `knowledge_refs` (node_ids del contexto/resultados).
2. El grafo llama al Memory Service (nuevo endpoint `POST /api/v1/thinking/episodes/...`) o, mejor,
   emite eventos (`com.mindos.agents.step.recorded`) que un consumidor del Memory persiste
   (mantiene la hexagonal: Agents no escribe la DB directamente).
3. Al cerrar, marca `ended_at`, `status`, `final_output`.
4. Vincula: si el agente **crea** conocimiento (una conclusión, una decisión), crea nodos
   `decision`/`learning` y relaciónalos (`DECIDES`, `EVIDENCES`) con las fuentes usadas.

**DoD:** ejecutar un goal deja un episodio con N pasos en la DB, con `knowledge_refs` que apuntan a
los nodos reales usados; el `final_output` queda ligado a las evidencias.

---

## F2-T3 · Endpoint `/explain` — "¿cómo llegué a esto?"

**Pasos:**
1. `GET /api/v1/thinking/explain/{node_id}` → recorre hacia atrás: nodo → aristas `DECIDES/EVIDENCES/
   DERIVED_FROM/ANSWERS` + episodios que lo produjeron → devuelve un árbol
   `{conclusión, hipótesis consideradas, evidencias (con fuentes), decisiones, pasos del agente}`.
2. `GET /api/v1/thinking/explain/episode/{episode_id}` → narra el episodio paso a paso.
3. Opcional: un endpoint que pide al LLM (`qwen3:8b`) redactar la explicación en prosa a partir del
   árbol estructurado (con citas a `node_id`/`source`).

**DoD:** para una conclusión generada por un agente, `/explain` devuelve las evidencias y decisiones
que la sustentan, con trazabilidad hasta las fuentes originales.

---

## F2-T4 · Cognitive Query API — las 7 preguntas insignia

**Por qué:** son la promesa central del producto. Implementa cada una como endpoint de primera clase
en el Memory Service (`/api/v1/cognitive/...`), combinando las capacidades de Fases 1-2.

| Pregunta | Endpoint | Implementación |
|---|---|---|
| ¿Qué pensaba hace 6 meses sobre X? | `GET /cognitive/past-thinking?topic=X&at=...` | Búsqueda semántica de X **filtrada por `created_at` alrededor de la fecha** + `as-of`. |
| ¿Cómo llegué a esta conclusión? | reusa `/explain/{node_id}` | Thinking Graph (F2-T3). |
| ¿Qué ideas similares tuve antes? | `GET /cognitive/similar?node_id=X` | KNN vectorial sobre `object_type in (idea, hypothesis)` ordenado por fecha. |
| ¿Qué decisiones tomé y por qué? | `GET /cognitive/decisions?topic=X` | Nodos `decision` + sus `DECIDES/EVIDENCES` + rationale. |
| ¿Qué respalda esta recomendación? | `GET /cognitive/support?node_id=X` | Cadena `SUPPORTS/EVIDENCES` + provenance. |
| ¿Qué contradicciones existen? | `GET /cognitive/contradictions?topic=X` | Aristas `CONTRADICTS` (F2-T5). |
| ¿Qué patrones aparecen en mi pensar? | `GET /cognitive/patterns` | Clustering + agente de reflexión (Fase 5); v1: temas y tipos más frecuentes por periodo. |

**Pasos:** crea el módulo `memory/src/application/services/cognitive_queries.py` con un método por
pregunta, cada uno con su test. Expón los endpoints y regístralos como **capacidades** (para que los
agentes y el MCP los usen).

**DoD:** las 7 rutas responden con datos reales sobre un dataset de prueba sembrado; cada una tiene test.

---

## F2-T5 · Detección de contradicciones

**Por qué:** único y de alto valor; "¿qué contradicciones hay en mi conocimiento?".

**Pasos:**
1. Servicio `contradiction_detector.py`: para un nodo/afirmación, recupera vecinos semánticos y
   pregunta al LLM (`qwen3:8b`, JSON) si hay contradicción lógica; si sí, crea arista `CONTRADICTS`
   con `metadata={rationale, confidence}`.
2. Modo **batch** (job) y modo **on-ingest** (al ingerir un `fact/hypothesis`, chequea contra el
   top-k más similar).
3. Emite evento `com.mindos.memory.contradiction.detected` para surfaceo (digest/dashboard).
4. Evita falsos positivos: umbral de similitud mínimo + confirmación LLM + registro auditable.

**DoD:** sembrando dos hechos opuestos ("el puerto es 443" / "el puerto es 8080") se crea una arista
`CONTRADICTS` entre ellos y `/cognitive/contradictions` la lista.

---

## F2-T6 · Objeto Decisión con rationale y evidencia

**Pasos:**
1. Al registrar una decisión (por agente o por el usuario vía API/Dashboard), crea nodo `decision`
   con `content` (qué se decidió), `metadata.rationale` (por qué), aristas `EVIDENCES` a las pruebas
   y `DECIDES` al objeto afectado (proyecto/idea).
2. Endpoint `POST /api/v1/cognitive/decision`.

**DoD:** registrar una decisión y recuperarla vía `/cognitive/decisions` con su rationale y evidencias.

---

## Cierre de Fase 2
- [x] F2-T1 modelo · [x] F2-T2 trazas · [x] F2-T3 explain · [x] F2-T4 cognitive API
- [x] F2-T5 contradicciones · [x] F2-T6 decisiones

**Hito:** en este punto MindOS ya **se siente** como la visión aunque no tenga dashboard ni WhatsApp:
responde las 7 preguntas y explica su razonamiento por API.

---

✅ **Fase 2 completa (2026-07-21).** 67/67 tests no-integration verdes (`ruff check .` limpio),
migración 0004 (`reasoning_episodes`/`reasoning_steps`) validada offline. Smoke test de cierre
(`memory/tests/test_phase2_smoke.py`) verificado end-to-end: un agente real (Agents+Memory
in-process vía `httpx.ASGITransport`) deja un episodio que `/explain` reconstruye con evidencia
y episodio de origen, y las 7 preguntas insignia responden con datos reales sobre un dataset
sembrado (ideas, evidencia, decisión con rationale, dos hechos contradictorios).

Escribir ese smoke test con un dataset heterogéneo (no aislado como los tests unitarios de cada
tarea) encontró y corrigió dos bugs reales del mecanismo, no solo del test — ver `plan/NOTAS.md`
(entradas "Cierre Fase 2"): (1) la detección de contradicciones comparaba un `fact` contra
candidatos de cualquier tipo (idea, decisión...), no solo otros `fact/hypothesis`; (2) el nodo
`outcome` que un agente promueve a conocimiento no quedaba enlazado a su episodio de origen en el
Thinking Graph (se añadió el paso `kind="conclude"`).

Pendiente (no bloqueante, igual que Fases 0-1): verificación *online* contra Postgres/Redis reales
y el test de integración con Ollama real de F2-T5, ambos sin poder ejecutarse en este entorno de
desarrollo (sin Docker; RAM insuficiente para `qwen3:8b` bajo carga). Ver Stage 2 en
`plan/07-runway-a-produccion.md`.
