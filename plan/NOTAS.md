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
