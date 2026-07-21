# NOTAS de ejecución

Registro de discrepancias entre el plan y la realidad del código, y de las decisiones tomadas
durante la ejecución. Regla global #10: si algo del plan choca con el código, **para y anótalo aquí** antes de
improvisar.

Formato por entrada:

## [FECHA] TAREA-ID — título corto
- **Discrepancia:** qué esperaba el plan vs. qué encontré.
- **Decisión:** qué hice y por qué.
- **Impacto:** archivos/tareas afectadas.

---

<!-- Añade entradas debajo -->

## [2026-07-21] F0-T4 — Alembic validado offline, falta verificación con Postgres real
- **Discrepancia:** en el entorno de desarrollo no hay Docker ni Postgres local (5432 cerrado), así que no se pudo aplicar `alembic upgrade head` contra una base real.
- **Decisión:** migración inicial escrita a mano (no autogenerate) y validada en **modo offline** (`alembic -c memory/alembic.ini upgrade head --sql`), que emite el DDL correcto: extensión vector, VECTOR(768), índice HNSW coseno, índice parcial de relaciones activas e índice temporal.
- **Pendiente (cuando haya Docker/Postgres):** levantar `infra/docker-compose.yml`, correr `alembic upgrade head` online, e ingerir con `DATABASE_TYPE=postgres` para el DoD completo de F0-T4.
- **Impacto:** `memory/alembic/*`, `memory/alembic.ini`, `models.py` (Vector=EMBEDDING_DIM), `requirements.txt`.

## [2026-07-21] F0-T4 — Migraciones NO se auto-ejecutan en el lifespan
- **Decisión:** en vez de auto-migrar en el arranque de la app (riesgoso), las migraciones se aplican con el servicio one-shot `migrate` del compose (F0-T9) o manualmente con `alembic upgrade head`. El README de operación (Fase 6 §10) lo documenta.

## [2026-07-21] F1-T4 — Corrección de semántica en `get_latest_node_version` (bug introducido en F1-T1)
- **Discrepancia:** la implementación original de F1-T1 filtraba `WHERE tombstoned_at IS NULL` **dentro** de la consulta de "última versión", ordenando después por `version DESC`. Al llegar a F1-T4 (archivar/restaurar) se hizo evidente que esto era incorrecto: si la versión más reciente de un nodo quedaba tombstoneada, la consulta **retrocedía silenciosamente** a una versión antigua activa en vez de ocultar el nodo — resucitando contenido desactualizado sin avisar.
- **Decisión:** se corrigió la semántica en ambos adaptadores (Pg + InMemory): primero se obtiene la versión de **mayor número** (sin filtrar por tombstone en la query), y solo entonces se decide si devolverla u ocultarla (`None`) según `include_archived` y el propio `tombstoned_at` de ESA versión. Se eliminó además `VectorStorePort.delete()` (código muerto, nunca invocado, y representaba un borrado físico que violaba el principio "nada se pierde"); el soft-delete vive enteramente en `DatabasePort` vía `tombstoned_at`.
- **Impacto:** `memory/src/application/ports/database.py`, `memory/src/infrastructure/database/repositories.py`, `memory/src/infrastructure/adapters/in_memory_database.py`, `memory/src/application/ports/vector_store.py` y sus 2 adaptadores. Ninguna migración de esquema (el campo `tombstoned_at` ya existía desde 0002). El índice `ix_versions_active` de la migración 0002 sigue siendo válido pero ya no es el que acelera este query específico (ahora sin filtro WHERE); queda disponible para una futura consulta tipo "listar nodos activos".

## [2026-07-21] F1-T5 — Calibración empírica del umbral de dedup (0.92) con nomic-embed-text
- **Discrepancia:** el plan sugería "similitud >= UMBRAL (config, p.ej. 0.92)" sin especificar qué tipo de similitud captura ese valor. Al escribir el test de integración con Ollama real, una PARÁFRASIS genuina (mismo hecho, vocabulario distinto) midió solo ~0.81 de similitud coseno con `nomic-embed-text` — por debajo del umbral.
- **Decisión:** se mantuvo el default en 0.92 (según lo sugerido) porque es el calibre correcto para duplicados **casi-verbatim** (mismo mensaje reenviado/recapturado, variaciones de mayúsculas/puntuación — medido ~0.99), que es el caso de uso principal (evitar nodos duplicados por reingesta accidental de WhatsApp/CLI). Detectar PARÁFRASIS semánticas con vocabulario distinto (0.81) es un problema distinto y más difícil (deduplicación conceptual, no textual) que queda fuera del alcance de F1-T5; podría abordarse a futuro con un umbral separado más bajo + confirmación LLM (similar al diseño de detección de contradicciones de Fase 2), no con similitud vectorial cruda.
- **Impacto:** `memory/tests/test_dedup.py` (test de integración usa variación menor, no paráfrasis); `memory/src/config.py` (`DEDUP_SIMILARITY_THRESHOLD=0.92` sin cambios). Ninguna decisión de producción bloqueada por esto.

## [2026-07-21] Cierre de Fase 1 (F1-T1 a F1-T8) — resumen
- **Estado:** las 8 tareas de la Fase 1 (Knowledge Core) quedaron completas y verificadas: 39/39 tests (`ruff check .` limpio), 2 migraciones nuevas (0002 objeto cognitivo rico, 0003 provenance) validadas offline, y un smoke end-to-end de cierre (`memory/tests/test_phase1_smoke.py`) que encadena ingesta rica → `/context` con citas → `/timetravel` → `/neighbors` → un agente ejecutando `search_knowledge` vía HTTP real contra una instancia auténtica del Memory Service (in-process, `httpx.ASGITransport`, sin mocks de handler).
- **Decisiones de diseño no explícitas en el plan original** (documentadas en el commit de cada tarea, resumidas aquí):
  - F1-T1: `ObjectType`/`ObjectStatus`/`RelationType` se declararon como `str, Enum` (no ENUM nativo de Postgres) para no requerir `ALTER TYPE` al agregar valores nuevos; se incluyeron ya los tipos del futuro Thinking Graph (Fase 2) para evitar una migración de enum a futuro.
  - F1-T5: modo `on_duplicate` default `link` crea nodo nuevo + `DUPLICATE_OF`; `new_version` reutiliza el `node_id` detectado (no crea relación, es el mismo nodo).
  - F1-T7: expansión de grafo usa similitud **heredada y decaída** desde el nodo semilla (no una similitud vectorial propia de cada vecino), ya que `VectorStorePort` no tiene un método "embedding por id"; documentado en el código como simplificación deliberada.
  - F1-T8: el contrato de `Executor.execute_step` cambió de `str` a `ExecutionResult(output, status)` para poder señalizar `pending_approval` sin magic strings; esto requirió también un enlace condicional nuevo en el grafo (`execute_step` → `review_step` | `END`) que no estaba explícito en el plan pero es necesario para el DoD.
- **Pendiente:** verificación *online* contra Postgres real (igual que Fase 0 — sin Docker en este entorno de desarrollo). Ver Stage 0/1 en `plan/07-runway-a-produccion.md`.

## [2026-07-21] F2-T2 — Registro de razonamiento vía HTTP directo, no vía Event Bus
- **Discrepancia:** el plan sugería (con preferencia explícita, "O, mejor") que Agents emita eventos (`com.mindos.agents.step.recorded`) que un consumidor de Memory persista, en vez de que Agents llame directo al endpoint HTTP del Thinking Graph. El motivo dado ("mantiene la hexagonal: Agents no escribe la DB directamente") aplica igual a ambas opciones — ninguna hace que Agents toque la DB de Memory directamente, la diferencia real es sync (HTTP) vs. async (evento + consumidor en segundo plano).
- **Decisión:** se implementó la llamada HTTP directa (`ReasoningRecorderPort` → `HttpReasoningRecorder` → `POST /api/v1/thinking/episodes/...`), best-effort (no interrumpe la ejecución del agente si Memory no responde). Motivos: (1) Redis no está disponible en este entorno de desarrollo, igual que Postgres, así que un consumidor en vivo no se podría verificar end-to-end; (2) el patrón HTTP directo ya es el establecido para `/context` (F1-T7) y el despacho de capacidades (F1-T8), manteniendo consistencia; (3) permite verificación end-to-end inmediata (ver `agents/tests/test_reasoning_trace_integration.py`, que corre Agents+Memory in-process vía `httpx.ASGITransport` y confirma el DoD completo). La infraestructura genérica de consumidores de eventos queda para la Fase 3 (`pipeline de ingestión`), donde sí es explícitamente requerida.
- **Impacto:** `agents/src/application/ports/reasoning_recorder.py`, `agents/src/infrastructure/adapters/{http,noop}_reasoning_recorder.py`. Ningún evento `com.mindos.agents.*` se publica todavía; si a futuro se quiere notificar a otros consumidores (dashboard/audit), se puede añadir sin romper este contrato.
- **Refactor relacionado (no pedido explícitamente, pero necesario para probar el DoD):** `agents/src/main.py`'s `execute_agent_goal` pasó de crear 4 `httpx.AsyncClient` ad-hoc a uno solo inyectado vía `Depends(get_http_client)`, compartido entre el fetch de contexto, el Executor, el Recorder y el registro del outcome. Habilita tanto la reutilización de conexión como `app.dependency_overrides` en tests de integración.
