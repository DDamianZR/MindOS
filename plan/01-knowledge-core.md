# Fase 1 — Knowledge Core: el modelo cognitivo que la visión exige

**Objetivo:** pasar de "nodos con texto" a **objetos cognitivos ricos** (con confianza,
importancia, evidencia, origen y estado), consultables en el tiempo, sin duplicados, con
contexto GraphRAG y ejecución real de capacidades.

**Precondición:** Fase 0 cerrada y verde.

---

## F1-T1 · Objeto cognitivo de primera clase

**Por qué:** la visión define atributos comunes (identificador, versiones, relaciones, contexto,
origen, **confianza, importancia, evidencia**, línea temporal) y tipos concretos (Idea, Nota,
Hipótesis, Insight, Hecho, Proyecto, Tarea, Pregunta, Decisión, Observación, Experiencia, Recurso).
Hoy solo hay `entity_type: str` + `metadata` genérico.

**Pasos:**
1. En `schemas/mindos_schemas/domain/` crea `ObjectType` (Enum) y `RelationType` (Enum) canónicos.
2. Amplía el modelo `DbCognitiveObject` / `DbObjectVersion` (`memory/.../models.py`):
   - `object_type` (enum, reemplaza el string libre; migra datos existentes a `note`).
   - En la **versión**: `confidence: float=0.5` (0-1), `importance: float=0.5` (0-1),
     `status: str` (`draft|active|hypothesis|fact|superseded|archived`), `evidence: JSONB` (lista de
     `{node_id|url|quote, weight}`), `salience: float` (calculado; ver Fase 5), `tombstoned_at` (nullable).
3. DTOs en `schemas/api/v1/memory_dto.py`: extiende `IngestKnowledgeRequest`/`SearchResultItem`
   con los nuevos campos (con defaults para no romper clientes).
4. Migración Alembic `add cognitive fields`.
5. Actualiza `save_node_version` (puerto + 2 adaptadores) para persistir los nuevos campos.

**DoD:** ingesta con `object_type=hypothesis, confidence=0.3, importance=0.8` persiste y se
recupera con esos valores; migración aplica sin pérdida de datos.

---

## F1-T2 · Provenance (trazabilidad de origen)

**Por qué:** habilita "¿qué conocimientos respaldan esto?" y "¿cómo llegó esto aquí?".

**Pasos:**
1. Nueva tabla `sources` (`id`, `kind` = `whatsapp|pdf|image|audio|web|cli|api|agent`, `uri`,
   `raw_ref`, `captured_at`, `metadata JSONB`).
2. En `DbObjectVersion` añade `source_id` (FK nullable a `sources`).
3. La ingesta acepta `source: {kind, uri, ...}` opcional; si viene, crea/reutiliza `sources` y
   enlaza la versión. Los eventos de comunicación (Fase 3) siempre generan un `source`.
4. Endpoint `GET /api/v1/memory/node/{id}/provenance` → cadena de fuentes + versiones.

**DoD:** una versión ingerida con `source.kind=pdf` devuelve su fuente en `/provenance`.

---

## F1-T3 · Consulta temporal "as-of" (viaje en el tiempo)

**Por qué:** requisito explícito de la visión ("reconstruir el estado del conocimiento en
cualquier fecha") y base de "¿qué pensaba hace 6 meses?".

**Pasos:**
1. `DatabasePort.get_node_version_asof(node_id, at: datetime)` → la versión vigente en esa fecha
   (la de mayor `created_at <= at`). Implementa en Pg (SQL) e InMemory.
2. `DatabasePort.query_relations_asof(node_id, at, max_depth)` → relaciones con
   `valid_from <= at AND (valid_to IS NULL OR valid_to > at)` (bitemporal).
3. Endpoint `GET /api/v1/memory/timetravel?at=2026-01-01&node_id=...` que devuelve el snapshot.
4. Test: nodo con v1 (enero) y v2 (marzo); `as-of febrero` devuelve v1; `as-of hoy` devuelve v2.

**DoD:** el test bitemporal pasa; relaciones respetan el intervalo de validez.

---

## F1-T4 · Soft-delete / tombstone global (nada se borra)

**Por qué:** principio #1. Hoy hay `delete()` duro de vectores.

**Pasos:**
1. Reemplaza `VectorStorePort.delete` y `delete_relation` por marcado (`tombstoned_at`/`valid_to`).
   El `delete` físico solo se permite en un job de mantenimiento explícito y auditado (no en API).
2. Las búsquedas y el Context Builder **excluyen** por defecto lo tombstoneado
   (`WHERE tombstoned_at IS NULL`), con flag `include_archived` para recuperarlo.
3. Endpoint `POST /node/{id}/archive` (soft) y `POST /node/{id}/restore`.

**DoD:** archivar un nodo lo saca de la búsqueda pero `include_archived=true` lo recupera; no
existe ninguna ruta de API que borre físicamente conocimiento.

---

## F1-T5 · Dedup semántico en ingest

**Por qué:** mantener el grafo limpio; "una idea similar previa" debe enlazarse, no duplicarse.

**Pasos:**
1. Antes de crear un nodo nuevo, embeddea el contenido y busca vecinos con similitud `>= UMBRAL`
   (config, p.ej. 0.92).
2. Si hay match fuerte y `node_id` no fue provisto: en vez de crear, ofrece 3 comportamientos por
   parámetro `on_duplicate` = `new_version` (versiona el existente) | `link` (crea nodo + relación
   `RELATED_TO`/`DUPLICATE_OF`) | `force_new`. Default: `link`.
3. Devuelve en la respuesta si hubo dedup y contra qué nodo.

**DoD:** ingerir dos textos casi idénticos produce, por defecto, un enlace `DUPLICATE_OF` en vez
de dos nodos aislados.

---

## F1-T6 · Catálogo tipado de relaciones

**Pasos:**
1. Usa `RelationType` (F1-T1): `PART_OF, RELATED_TO, DERIVED_FROM, SUPPORTS, CONTRADICTS,
   CAUSED_BY, DUPLICATE_OF, MENTIONS, ANSWERS, EVIDENCES, DECIDES, LEADS_TO`.
2. Valida el tipo en `save_relation`; rechaza tipos fuera del catálogo (o márcalos `CUSTOM`).
3. Endpoint `POST /api/v1/memory/relation` (crear) y `GET /node/{id}/neighbors?depth=2`.

**DoD:** crear una relación `SUPPORTS` entre dos nodos y recuperarla en `/neighbors`.

---

## F1-T7 · Context Builder v2 (GraphRAG con citas)

**Por qué:** es lo que alimenta la calidad de todo agente. Hoy es básico (vector + 1 salto).

**Pasos (en `context_builder.py`):**
1. Recupera candidatos por vector (top-k) **y** expande por grafo (vecinos hasta `depth`),
   deduplicando nodos.
2. **Reranking** por combinación: `score = w1*similitud + w2*importance + w3*recencia + w4*confidence`
   (pesos configurables). Añade recencia = decaimiento exponencial sobre `created_at`.
3. Incluye una **sección temporal**: hitos/versiones recientes relevantes (timeline corto).
4. Devuelve **estructura + citas**: cada fragmento lleva `node_id`, `version`, `source_id` para que
   el agente pueda citar ("según [n1]…"). Cambia el retorno de `str` a un `ContextBundle` (DTO)
   con `.to_prompt()` que serializa el texto para el LLM y `.citations` para trazabilidad.
5. Actualiza `agents/src/main.py` para consumir el nuevo contexto (vía HTTP a un nuevo endpoint
   `POST /api/v1/memory/context` que expone el Context Builder).

**DoD:** `/context` devuelve fragmentos con `node_id`+`source` y un orden que refleja los pesos;
un test verifica que un nodo de alta `importance` sube en el ranking frente a uno de baja.

---

## F1-T8 · Executor real (despacho de capacidades) + gate de aprobación

**Por qué:** hoy el Executor solo simula; no llama a los endpoints reales de las capacidades.

**Pasos (en `capability_executor.py`):**
1. Si la capacidad tiene `endpoint_path` HTTP, despáchala con `httpx` al `provider_service`
   (resuelve host por config: `memory`→`MEMORY_URL`, etc.), pasando `inputs` como body/params
   según su `parameters_schema`. Propaga `X-Correlation-Id`.
2. Respeta `requires_approval`: si es `true`, no ejecutes; devuelve estado `pending_approval` y
   emite evento `com.mindos.agents.approval.requested`. (La aprobación se resuelve en Fase 3/4 vía
   Gateway/Dashboard.)
3. Mantén los mock handlers solo para tests.
4. Registra cada ejecución como paso del futuro Thinking Graph (Fase 2) — por ahora, loguea
   entrada/salida con `correlation_id`.

**DoD:** un plan cuyo paso usa `search_knowledge` hace una llamada HTTP real al Memory Service y
devuelve resultados reales; una capacidad con `requires_approval=true` queda en `pending_approval`.

---

## Cierre de Fase 1
- [x] F1-T1 objeto rico · [x] F1-T2 provenance · [x] F1-T3 as-of · [ ] F1-T4 soft-delete
- [ ] F1-T5 dedup · [ ] F1-T6 relaciones tipadas · [ ] F1-T7 GraphRAG · [ ] F1-T8 executor real

**Verificación:** ingesta rica → búsqueda con citas → `timetravel` → `neighbors` → un agente que
recupera contexto real y ejecuta `search_knowledge` de verdad. Todo con `pytest` verde.
