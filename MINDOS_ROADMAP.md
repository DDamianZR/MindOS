# MindOS — Diagnóstico de estado y Roadmap detallado

> Documento de auditoría técnica frente a la visión teórica del KOS.
> Fecha: 2026-07-20. Basado en lectura completa del código (~3.100 líneas Python).

---

## 1. Veredicto ejecutivo

**El proyecto NO cumple todavía la visión teórica — y es esperable: está en la transición entre las fases "Simulación" y "Persistencia" de tu propio plan evolutivo.**

Lo que existe está bien pensado arquitectónicamente (hexagonal real, puertos/adaptadores limpios, LangGraph funcionando, logging con trazabilidad). Pero lo construido es el **andamiaje del kernel**, no el producto. Los componentes que hacen a MindOS *distinto* de "otro chatbot con memoria" —Thinking Graph, explicabilidad del razonamiento, consultas cognitivas, detección de contradicciones, captura multi-canal— **no existen**. Además, 7 de los ~15 módulos previstos están vacíos (solo `.git`), el Event Bus está escrito pero **no conectado a nada**, y el modo PostgreSQL **no arranca** (no hay creación de tablas).

Estimación honesta de avance frente a la visión completa: **~7-10%** (kernel y simulación), con una base sólida para construir el resto.

---

## 2. Mapa de cumplimiento (visión → realidad)

Leyenda: ✅ hecho · 🟡 parcial/simulado · 🔴 ausente · 🐞 con bug

### 2.1 Principios filosóficos

| Principio | Estado | Nota |
|---|---|---|
| El conocimiento nunca se pierde | 🟡🐞 | Versiones append-only ✅, pero hay `delete()` duro de vectores y no hay política global de tombstone. Lineaje de versiones roto (bug). |
| El conocimiento evoluciona | 🔴 | No hay máquina de estados Idea→Proyecto, Hipótesis→Hecho, Fracaso→Aprendizaje. Solo versionado de texto. |
| El razonamiento importa más que la respuesta | 🔴 | El agente produce `final_output` pero **no persiste ni explica** qué información/relaciones/hipótesis usó. Sin Thinking Graph. Es el mayor hueco frente a la visión. |
| La IA nunca es el centro (proveedor reemplazable) | ✅ | `LlmPort` + adaptador Ollama + mock. Bien abstraído. |
| Todo es reemplazable (Ports & Adapters) | ✅ | Hexagonal aplicado correctamente en `memory` y `agents`. |
| Kernel First | ✅ | El orden de construcción respeta la filosofía. |

### 2.2 Arquitectura conceptual (dominios)

| Dominio | Estado | Nota |
|---|---|---|
| Knowledge Core | 🟡 | Nodos + versiones + relaciones temporales + búsqueda vectorial. Falta modelo cognitivo rico (confianza/importancia/evidencia/origen). |
| Communication Layer | 🔴 | Carpeta `whatsapp/` vacía. Eventos de comunicación definidos en schemas, pero **cero** adaptadores (WhatsApp/Telegram/CLI/email). |
| Reasoning Layer | 🟡 | Planner→Executor→Reviewer con LangGraph funciona **en simulación**. El Executor no despacha de verdad (solo mocks). |
| Gateway | 🔴 | Vacío. Sin punto de entrada único, sin auth, sin validación, sin routing. |
| Dashboard | 🔴 | Vacío. Sin grafo, sin timeline, sin explorador de memoria. |
| Mobile | 🔴 | Vacío. |
| MCP | 🔴 | Vacío. No se exponen capacidades vía Model Context Protocol. |

### 2.3 Modelo cognitivo y grafos

| Elemento | Estado | Nota |
|---|---|---|
| Objetos cognitivos (Idea, Hipótesis, Decisión…) | 🟡 | Existe `entity_type: str` genérico + `metadata` JSONB. No hay tipos de primera clase ni atributos comunes (confianza, importancia, evidencia, origen). |
| Versionado | 🟡🐞 | Snapshots por versión ✅. Bug: `parent_version_id` apunta al `node_id` en vez de a la versión previa → lineaje roto. IDs de versión no deterministas (`hash()`). |
| Knowledge Graph | 🟡 | Tabla `relations` bitemporal (`valid_from/valid_to`) + recorrido recursivo ✅. Falta tipado de relaciones y catálogo. |
| Thinking Graph | 🔴 | No existe. Ni Pregunta→Hipótesis→Evidencia→Decisión→Resultado→Aprendizaje. |
| Memoria temporal ("estado en fecha X") | 🔴 | La consulta bitemporal "reconstruir conocimiento a fecha X" **no está implementada** pese a ser requisito explícito. |
| Context Builder | 🟡 | Combina vector + grafo ✅ básico. Falta timeline, recencia, importancia, citas y ponderación. |
| Capability Registry | 🟡 | Registro/descubrimiento funciona, pero solo in-memory y sin persistencia ni salud. |
| Planner→Executor→Reviewer | 🟡 | Ciclo con replan funciona. Falta ejecución real y límite de reintentos (riesgo de bucle). |

### 2.4 Infraestructura transversal

| Elemento | Estado | Nota |
|---|---|---|
| Event Driven | 🔴🐞 | Schemas CloudEvents ✅, `RedisEventBus` implementado ✅ **pero no se usa en ningún servicio**. La ingesta no emite eventos ni escribe el `event_log`. |
| CQRS | 🔴 | Declarado, no implementado. Hoy son endpoints CRUD. |
| Event Sourcing / auditoría | 🔴🐞 | `save_event_log` definido pero **nunca invocado**. |
| Observabilidad | 🟡 | Logging estructurado + `correlation_id` propagado ✅. Falta tracing (OTel) y métricas. |
| Persistencia real | 🟡🐞 | Adaptadores Postgres/pgvector escritos, pero **no hay migraciones ni `create_all`** → modo `postgres` revienta al primer query. |
| Embeddings reales | 🔴 | Solo `MockEmbedding`. No hay adaptador Ollama `nomic-embed-text`. |
| OCR / Storage reales | 🔴 | Solo mocks/in-memory. Sin ingestión real de PDF/imagen/audio. |
| Orquestación | 🟡 | `docker-compose` solo levanta Postgres + Redis. Los servicios no están dockerizados ni orquestados. |
| Seguridad / multiusuario | 🔴 | Inexistente. |
| Tests / CI | 🟡 | 3 tests verdes (bien), pero cobertura mínima y sin CI. |

### 2.5 Las 7 preguntas insignia de la visión

Ninguna está implementada. Son **el alma del producto** y hoy no hay ninguna funcionalidad que las responda:

1. ¿Qué estaba pensando hace seis meses sobre X? → 🔴 (requiere consulta temporal + timeline)
2. ¿Cómo llegué a esta conclusión? → 🔴 (requiere Thinking Graph + trazas de razonamiento)
3. ¿Qué ideas similares tuve antes? → 🟡 (búsqueda vectorial existe; falta "a lo largo del tiempo")
4. ¿Qué decisiones tomé y por qué? → 🔴 (requiere objeto Decisión con evidencia + rationale)
5. ¿Qué conocimientos respaldan esta recomendación? → 🔴 (requiere citas/provenance)
6. ¿Qué contradicciones existen en mi conocimiento? → 🔴 (requiere detección de contradicciones)
7. ¿Qué patrones aparecen en mi forma de pensar? → 🔴 (requiere agente de reflexión/consolidación)

---

## 3. Bugs y deudas críticas ya presentes

Ordenados por impacto. Estos deben arreglarse **antes** de construir encima.

1. **Lineaje de versiones roto** — `memory/src/main.py:144`: se pasa `latest_ver["node_id"]` como `parent_version_id`, pero ese campo debe apuntar a la **versión** anterior (FK a `knowledge_node_versions.id`), no al nodo. Rompe la reconstrucción histórica.
2. **IDs no deterministas con `hash()`** — `repositories.py:46` y `event_bus.py:37` generan UUIDs con `UUID(int=hash(...))`. `hash()` de strings está *salteado por proceso* (PYTHONHASHSEED) → IDs irreproducibles y con colisiones (mismo `event_type+correlation_id` ⇒ siempre el mismo "ID único" ⇒ eventos duplicados). **Usar `uuid.uuid7()`** (ya disponible en Python 3.14 de esta máquina — verificado).
3. **Modo PostgreSQL no arranca** — no hay Alembic ni `Base.metadata.create_all`, ni `CREATE EXTENSION vector`, ni índice vectorial. `DATABASE_TYPE=postgres` da error al primer acceso.
4. **La ingesta no es event-driven** — no publica eventos ni escribe `knowledge_event_log`, contradiciendo el principio rector. `save_event_log` nunca se llama.
5. **Score vectorial falso** — `pgvector.py:57` devuelve `score=1.0` fijo; se pierde el ranking real de similitud en el camino Postgres.
6. **`created_at` de respuesta incorrecto en ingest** — devuelve el timestamp de la versión *anterior*, no el de la recién creada.
7. **UUIDv7 prometido, `uuid4()` usado** — comentarios dicen "UUIDv7" en todo el código pero se usa `uuid4()`. Con 3.14 basta `uuid.uuid7()` (ordenable temporalmente → mejor para timeline e índices).
8. **Sin tope de reintentos en el grafo** — `_should_continue` puede alternar replan↔execute indefinidamente si el Reviewer nunca aprueba. Falta contador y corte.
9. **Executor no ejecuta de verdad** — `capability_executor.py` solo tiene mocks o devuelve un string de simulación; no hace la llamada HTTP al `endpoint_path` de la capacidad ni respeta `requires_approval`.
10. Menores: `version: '3.8'` obsoleto en compose; `import` dentro de funciones (`main.py`); lógica de ramas frágil en `MockLlm` por precedencia `and/or`.

---

## 4. Roadmap por fases

Respeta tu estrategia (Kernel → Simulación → Persistencia → Inteligencia → Automatización → Expansión). Hoy estás al final de "Simulación". Cada fase entrega algo ejecutable.

### Fase 0 — Estabilizar el Kernel (correcciones) · ~1 semana
Objetivo: que lo que ya existe sea correcto, persistente y arrancable.
- [ ] Migrar todos los IDs a `uuid.uuid7()`; eliminar los `hash()`.
- [ ] Corregir `parent_version_id` (apuntar a la versión previa real).
- [ ] Alembic + migración inicial; `CREATE EXTENSION vector`; índice HNSW/IVFFlat; script `create_all` para dev.
- [ ] Emitir eventos en ingest/update/relation: escribir `event_log` **y** publicar en el Event Bus. Cablear `RedisEventBus` en el Memory Service.
- [ ] Adaptador de embeddings real (Ollama `nomic-embed-text`) detrás de `EmbeddingPort`; dimensión configurable.
- [ ] Devolver score de similitud real desde pgvector.
- [ ] Dockerfiles para `memory` y `agents`; que `docker compose up` levante el sistema completo.
- [ ] Tope de reintentos en el grafo del agente.
- [ ] CI mínimo: `ruff` + `pytest` en cada push.

### Fase 1 — Knowledge Core completo · ~2-3 semanas
Objetivo: el modelo cognitivo rico que la visión exige.
- [ ] Objeto cognitivo de primera clase con atributos comunes: `object_type` (Idea, Nota, Hipótesis, Insight, Hecho, Proyecto, Tarea, Pregunta, Decisión, Observación, Experiencia, Recurso…), `confidence`, `importance`, `status` (draft/active/archived/superseded), `evidence[]`, `provenance` (evento/fuente de origen).
- [ ] Consulta bitemporal **"as-of"**: reconstruir el estado del conocimiento a cualquier fecha (usa `valid_from/valid_to` + versiones).
- [ ] Política global de **soft-delete/tombstone** (nunca borrado duro); quitar el `delete()` destructivo.
- [ ] **Dedup semántico** en ingest: si algo es casi-idéntico, versionar/enlazar en vez de duplicar.
- [ ] Catálogo tipado de relaciones (`PART_OF`, `RELATED_TO`, `CONTRADICTS`, `SUPPORTS`, `DERIVED_FROM`, `CAUSED_BY`…).
- [ ] Context Builder v2 (GraphRAG): vector + caminata de grafo + timeline + ponderación por recencia/importancia; devuelve contexto estructurado **con citas**.
- [ ] Executor real: despacho HTTP al `endpoint_path`, con gate de aprobación para `requires_approval`.

### Fase 2 — Thinking Graph y Explicabilidad · ~3 semanas · **el diferenciador**
Objetivo: que MindOS explique *cómo* piensa, no solo *qué* responde.
- [ ] Modelo del Thinking Graph: nodos (Pregunta, Hipótesis, Investigación, Evidencia, Decisión, Resultado, Aprendizaje) y aristas de razonamiento.
- [ ] Persistir la traza del agente (cada corrida Planner/Executor/Reviewer = un "episodio de razonamiento") dentro del Thinking Graph, ligada al Knowledge Graph.
- [ ] Endpoint **`/explain`**: "¿cómo llegué a la conclusión X?" recorriendo el Thinking Graph.
- [ ] **Cognitive Query API**: las 7 preguntas insignia como endpoints de primera clase.
- [ ] Agente de **detección de contradicciones** (embeddings + verificación con LLM) que crea aristas `CONTRADICTS` y las surfacea.

### Fase 3 — Gateway, Auth y Communication Layer · ~3-4 semanas
Objetivo: capturar desde cualquier canal; un único punto de entrada seguro.
- [ ] Gateway: entrada única, autenticación (single-user token para empezar), rate-limit, validación, routing, originación del `correlation_id`.
- [ ] Adaptadores de comunicación: CLI y REST primero; luego WhatsApp (Baileys/whatsapp-web.js o Meta Cloud API) → **todos** emiten `MessageReceivedEvent`.
- [ ] Pipeline de ingestión (consumidor de eventos): evento → OCR/transcripción → embedding → almacenamiento → enlazado automático.
- [ ] Adaptadores reales: OCR (Tesseract/Paddle), transcripción de audio (Whisper), Storage (FS local / MinIO).

### Fase 4 — Interfaces (Dashboard, MCP, Mobile) · ~4 semanas
Objetivo: ver, navegar y exponer el conocimiento.
- [ ] Dashboard: visualización de grafo (Cytoscape/Sigma), explorador de memoria, timeline, visor de trazas de razonamiento, búsqueda.
- [ ] **Servidor MCP**: exponer `search_knowledge`, las consultas cognitivas e `ingest` como herramientas MCP → que Claude u otros asistentes usen MindOS como memoria de largo plazo.
- [ ] Mobile: PWA de captura rápida.

### Fase 5 — Automatización y Evolución · continuo
Objetivo: que el sistema evolucione con vos.
- [ ] **Agente de reflexión/consolidación** (periódico, tipo "sueño"): resume, enlaza, deduplica, detecta patrones, ajusta salience (refuerzo/decaimiento de importancia).
- [ ] **Resurfacing/digest**: reflotar ideas dormidas pero relevantes (repetición espaciada) — encarna "una idea mala puede volverse clave años después".
- [ ] Agente de investigación: multi-paso, escribe hallazgos en el Thinking Graph.
- [ ] Lifecycle automatizado: Hipótesis→Hecho, Idea→Proyecto, Proyecto→Aprendizaje.
- [ ] Harness de evaluación de calidad de razonamiento.

### Transversal (durante todo el camino)
- [ ] CQRS real cuando se justifique (separar modelos de comando y consulta).
- [ ] Cifrado en reposo, backups, soberanía de datos (coherente con tu principio de privacidad).
- [ ] Observabilidad con OpenTelemetry (trazas + métricas).

---

## 5. Funcionalidades que recomiendo añadir (más allá de la visión original)

Ordenadas por relación valor/esfuerzo:

1. **Cognitive Query API** (las 7 preguntas como endpoints) — es la promesa central; hoy no existe. *Alto valor.*
2. **Thinking Graph + trazas persistidas** — convierte cada respuesta en algo explicable y consultable después. *El diferenciador.*
3. **Provenance / trazabilidad de origen** — cada objeto enlaza a su evento/fuente (mensaje WhatsApp, PDF…). Habilita "¿qué respalda esto?". *Barato y habilitante.*
4. **Consulta temporal "time-travel"** — reconstruir el estado a fecha X. Requisito explícito, hoy ausente. *Medio.*
5. **Detección de contradicciones** — agente que enlaza `CONTRADICTS` y avisa. *Alto valor, único.*
6. **Reflexión/consolidación periódica** — "consolidación de memoria" al estilo humano: resume, enlaza, detecta patrones. *Alto valor a largo plazo.*
7. **Resurfacing espaciado** — reflotar conocimiento dormido relevante. *Diferenciador emocional.*
8. **GraphRAG formal** en el Context Builder — vector + grafo + tiempo con citas. *Mejora todo aguas abajo.*
9. **Dedup semántico en ingest** — evita ruido; mantiene el grafo limpio. *Medio.*
10. **Servidor MCP** — que asistentes externos (Claude incluido) usen MindOS como su memoria. *Alto apalancamiento.*
11. **Confianza/importancia con decaimiento y refuerzo** — "salience" que cambia según se refuerza o contradice. *Medio.*
12. **Replay desde el event log** — event sourcing real: reconstruir proyecciones desde eventos. *Robustez.*
13. **Cifrado local + backups** — coherente con soberanía de datos. *Medio.*

---

## 6. Recomendación de arranque

Empezar por **Fase 0** (correcciones) porque hay bugs que invalidan la persistencia y contradicen los principios (event-driven, "nada se pierde"). Con el kernel estable, la **Fase 2 (Thinking Graph + Cognitive Query API)** es lo que primero hará que MindOS *se sienta* como la visión y no como "otra app de notas", aun antes de tener dashboard o WhatsApp.

Orden sugerido de máximo impacto temprano: **Fase 0 → un slice vertical de Fase 1 (modelo rico + provenance) → Fase 2 (explicabilidad).**
