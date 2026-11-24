# Modelo de dominio y diagramas de actividades de MindOS (UML)

Diagramas **como código** (PlantUML), derivados de la lectura del código real de `schemas/`, `memory/`,
`agents/` y `comms/` — no de la visión original. Los SVG renderizados están en [`out/`](out/).

```bash
python docs/modelo-dominio/render.py          # regenera out/*.svg (requiere Java 11+)
python docs/modelo-dominio/render.py check    # solo valida la sintaxis
```

## 1. Modelo de dominio — diagramas de clases

| Diagrama | Qué muestra |
|---|---|
| [00 · Vista integrada](out/00-modelo-dominio.svg) | Entidades de negocio de los cuatro contextos y cómo se asocian (conceptual, sin ruido). |
| [01 · Conocimiento](out/01-conocimiento.svg) | `ObjetoCognitivo` → `VersionObjeto` (inmutable), `Relacion` temporal, `Fuente` (provenance), `Evidencia`, `EventoLog` y los catálogos `ObjectType`, `ObjectStatus`, `RelationType`, `SourceKind`. |
| [02 · Razonamiento y agentes](out/02-razonamiento-agentes.svg) | Thinking Graph (`EpisodioRazonamiento`, `PasoRazonamiento`), `Plan`, `Capacidad`, `SolicitudAprobacion` y el grafo Planner/Executor/Reviewer. |
| [03 · Comunicación y eventos](out/03-comunicacion-eventos.svg) | Mensajes entrantes/salientes, canales (CLI, REST, WhatsApp), `CloudEvent<T>` y los eventos de dominio por stream. |
| [04 · Servicios de IA y puertos](out/04-servicios-ia-puertos.svg) | Servicios de aplicación con IA (ingesta, contradicciones, GraphRAG, explicabilidad, consultas cognitivas), sus puertos y adaptadores. |

Decisiones de modelado visibles en los diagramas: nada se borra (archivar = *tombstone*); actualizar =
nueva versión con `parentVersionId`; el catálogo de tipos se guarda como texto (no ENUM de BD); el
episodio de razonamiento registra el *proceso* y los objetos cognitivos el *resultado*, unidos por
`nodosCitados`.

## 2. Diagramas de actividades

Dos grupos: **procesos de negocio** (escenarios de caso de uso, con carriles por actor/servicio) y
**algoritmos de IA** (el flujo interno de cada algoritmo, con umbrales y modos de falla reales).

| Diagrama | Tipo | Caso de uso / algoritmo | Código de referencia |
|---|---|---|---|
| [A1 · Captura multimodal](out/A1-captura-multimodal.svg) | Negocio | Capturar conocimiento por WhatsApp/CLI/REST (OCR, STT, clasificación de pregunta, respuesta por el mismo canal) | `memory/src/application/services/ingestion_pipeline.py` |
| [A2 · Ingesta, dedup y versionado](out/A2-ingesta-dedup-versionado.svg) | IA + negocio | Deduplicación semántica (umbral 0,92), versionado, provenance, eventos | `memory/src/main.py` (`/memory/ingest`) |
| [A3 · Contradicciones](out/A3-deteccion-contradicciones.svg) | **IA** | Doble compuerta: similitud ≥ 0,65 → juicio del LLM; falla cerrado | `contradiction_detector.py` |
| [A4 · Auto-enlazado](out/A4-auto-enlazado.svg) | **IA** | Relaciones por similitud + confirmación del LLM con catálogo restringido | `ingestion_pipeline.py` (`_auto_link`) |
| [A5 · Contexto GraphRAG](out/A5-graphrag-contexto.svg) | **IA** | Semillas vectoriales + expansión por grafo + reranking (0,5/0,2/0,15/0,15) + citas `[n1]` | `context_builder.py` |
| [A6 · Ciclo Planner→Executor→Reviewer](out/A6-ciclo-planner-executor-reviewer.svg) | **IA** | Agente LangGraph con replanificación (máx. 3 reintentos) y traza en el Thinking Graph | `agents/src/domain/planner/agent_graph.py`, `agents/src/main.py` |
| [A7 · Aprobación humana](out/A7-aprobacion-humana.svg) | Negocio | Acción sensible pausada hasta que el usuario aprueba o rechaza | `capability_executor.py`, `approvals_router.py` |
| [A8 · Explicabilidad](out/A8-explicabilidad.svg) | Algoritmo | "¿Cómo llegué a esto?": recorrido hacia atrás con anti-ciclos y provenance | `explainability.py` |

## 3. Alcance y límites

- Solo se modela lo **implementado** (Fases 0–4 del plan). La Fase 5 (consolidación nocturna,
  resurfacing, lifecycle `hypothesis → fact`) está planificada en `plan/05-automatizacion.md` y **no**
  se dibuja como si existiera.
- **Observación hallada al diagramar A6:** `PlannerExecutorReviewerGraph` no tiene arista condicional
  tras `plan_step`; si el Planner falla, el grafo avanza a `execute_step` con `steps = []` y
  `state["steps"][idx]` lanza `IndexError` fuera del `try` (termina en HTTP 500). Está anotado en el
  propio diagrama; no se modificó el código.
- Los nombres de clases y atributos están en español para el documento; los del código (inglés) se
  indican en las tablas de referencia.
- Complementa el diagrama C4 ([`docs/c4`](../c4)), que cubre contexto y contenedores.
