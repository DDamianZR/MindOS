# NOTAS de ejecución

Registro de discrepancias entre el plan y la realidad del código, y decisiones tomadas por el
ejecutor. Regla global #10: si algo del plan choca con el código, **para y anótalo aquí** antes de
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
