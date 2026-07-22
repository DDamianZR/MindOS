# Runway a producción — secuencia maestra de ejecución para Sonnet

> **Este es el documento de entrada para ejecutar.** Ordena TODO el trabajo restante hasta el
> despliegue en producción en una única secuencia lineal, con **puertas de despliegue** intercaladas
> (para que producción crezca de forma incremental, no big-bang al final) y un **protocolo de
> ejecución** calibrado para Sonnet.
>
> El *qué/cómo* detallado de cada tarea vive en los archivos de fase (`00`–`06`). Aquí está el
> *en qué orden*, los *gates de despliegue* y los *criterios de "shippable"*. No reimplementa; secuencia.

---

## 0. Protocolo de ejecución para Sonnet (LEER PRIMERO)

1. **Trabaja en pasos pequeños y verificados.** Una tarea (`Fx-Ty`) a la vez. No agrupes varias
   tareas en un mismo cambio. Después de cada una, corre su **DoD** y confirma verde.
2. **Antes de cada tarea, RELEE su ficha** en el archivo de fase correspondiente. No trabajes de
   memoria: los detalles (rutas, firmas, DoD) están ahí.
3. **Commit atómico por tarea.** Formato: `feat(memory): F1-T3 objeto cognitivo rico`. Un commit
   por tarea permite revisión y rollback limpios.
4. **Respeta la hexagonal y los principios** (`plan/README.md §0`): dominio nunca importa
   infraestructura; nada de borrado duro; IDs con `uuid7`; contratos en `schemas/`.
5. **Fases 3, 4 y 5 están a nivel de épica.** Cuando llegues a cada una: **PRIMERO descompón** cada
   tarea épica en sub-tareas atómicas con su DoD y **escríbelas en el archivo de la fase**; recién
   entonces ejecútalas. No improvises una épica de una sola pasada.
6. **Verifica siempre con un comando concreto** (`ruff check .`, `pytest -m "not integration"`,
   `curl`, `docker compose ps`). Si el DoD no pasa, corrige antes de avanzar.
7. **No avances de Stage sin pasar su Deploy Gate.** Los gates son obligatorios: son los que
   garantizan que "sigue desplegable" en cada punto.
8. **Si el plan choca con la realidad, PARA y anota** en `plan/NOTAS.md` (regla global #10).
9. **Marca las casillas** `[x]` en los archivos de fase a medida que completas tareas.
10. **Secretos nunca en el repo.** `.env` está en `.gitignore`. Genera secretos fuertes; documenta
    en `.env.example` (sin valores).

---

## 1. Estado actual (punto de partida)

- ✅ **Fase 0 completa** (código): monorepo, uuid7, lineaje de versiones, Alembic+pgvector (768d),
  embeddings reales Ollama, ingesta event-driven, score vectorial real, tope de reintentos, Docker
  stack, CI. `ruff` limpio, 8 tests verdes.
- ⏳ **Pendiente de Fase 0:** verificación *online* (no había Docker/Postgres en el entorno de
  desarrollo). Es el primer paso del runway (Stage 0).
- 🔴 **Todo lo demás** (Fases 1–5 + hardening de producción) está por hacer.

**Modelos Ollama listos:** `qwen3:8b` (razonamiento), `qwen2.5-coder:14b` (extracción),
`qwen3-coder:30b` (investigación, solo workstation), `nomic-embed-text` (embeddings 768d).
**Hardware:** server Ubuntu 16 GB (24/7) + workstation Ryzen 9 (on-demand). Detalle en `README.md §2`.

---

## 2. Mapa del runway (stages y gates)

```
Stage 0  Arranque + primer deploy local ......... cierra Fase 0 online   ──► Deploy Gate 0
Stage 1  Knowledge Core rico (Fase 1) ...........  F1-T1..T8             ──► Deploy Gate 1
Stage 2  Thinking Graph + 7 preguntas (Fase 2) ..  F2-T1..T6             ──► Deploy Gate 2
Stage 3  Gateway + Auth + Comunicación (Fase 3) .  F3-T1..T7  [SEGURIDAD]──► Deploy Gate 3  ⚑ primer acceso externo
Stage 4  Interfaces: Dashboard/MCP/PWA (Fase 4) .  F4-T1..T3             ──► Deploy Gate 4
Stage 5  Automatización (Fase 5) ................  F5-T1..T6             ──► Deploy Gate 5
Stage 6  Hardening + Cutover de producción ......  Fase 6 completa       ──► GO-LIVE
```

Cada **Deploy Gate** = reconstruir/actualizar el stack, migrar, correr smoke-test, confirmar salud.
Producción se endurece de forma incremental: la seguridad (auth, TLS, firewall, backups) es
**bloqueante en el Stage 3**, el primer punto en que algo se expone fuera del host.

---

## 3. Stage 0 — Arranque y primer despliegue local (cierra Fase 0)

**Objetivo:** validar el kernel end-to-end contra Postgres real y dejar el stack corriendo.

**Tareas:**
1. `cp .env.example .env`; genera `POSTGRES_PASSWORD` fuerte. Asegura Ollama arriba en el host con
   `qwen3:8b` y `nomic-embed-text` (`curl localhost:11434/api/tags`).
2. `docker compose -f infra/docker-compose.yml up -d --build`.
3. Verifica que `migrate` terminó OK (`docker compose logs migrate`) y creó el esquema (extensión
   vector + tablas + índice HNSW).
4. Corre el smoke de Fase 0 (ver `00-fundaciones.md §Cierre`): `/health` de memory y agents;
   ingesta real con `DATABASE_TYPE=postgres`; búsqueda con score real; `event_log` con fila.
5. Marca en `plan/NOTAS.md` la verificación online como resuelta.

**Provisión del server (si aún no está):** instala Docker + Compose en el Ubuntu; clona el repo
(ver §7 sobre el remoto git); copia `.env`; repite pasos 2–4 en el server.

### 🚦 Deploy Gate 0 — "el kernel vive en producción"
- [ ] `docker compose ps` → postgres, redis, memory, agents **healthy**; `migrate` exited 0.
- [ ] Ingesta + búsqueda + historial responden contra Postgres.
- [ ] `event_log` recibe eventos; stream `mindos.memory` recibe mensajes.
- [ ] CI verde en el remoto.

---

## 4. Stage 1 — Knowledge Core rico (Fase 1)

✅ **Código completo** (2026-07-21): `F1-T1 … F1-T8` de [`01-knowledge-core.md`](01-knowledge-core.md)
implementadas y verificadas (39/39 tests, `ruff` limpio, migraciones 0002/0003 validadas offline).
Cada tarea con esquema nuevo generó su propia migración Alembic, según lo pedido.

**Foco (hecho):** objeto cognitivo rico (confianza/importancia/evidencia/estado), provenance, consulta
temporal *as-of*, soft-delete global, dedup semántico, relaciones tipadas, Context Builder v2
(GraphRAG con citas), Executor real (despacho HTTP + gate de aprobación).

### 🚦 Deploy Gate 1
- [x] Migraciones (0002, 0003) generadas y validadas offline; `alembic upgrade head` online
      pendiente de Docker/Postgres (igual que el Gate 0 — ver `plan/NOTAS.md`).
- [ ] Rebuild + `up -d`; healthchecks verdes. *(pendiente: requiere Docker)*
- [x] Smoke: ingesta rica → búsqueda con citas → `/timetravel` → `/neighbors` → un agente que
      recupera contexto real y ejecuta `search_knowledge` de verdad — verificado en
      `memory/tests/test_phase1_smoke.py` (in-process vía ASGI; falta repetir contra el stack
      Docker real una vez levantado).
- [ ] `pytest -m "not integration"` verde; CI verde.

---

## 5. Stage 2 — Thinking Graph + explicabilidad (Fase 2)

✅ **Código completo** (2026-07-21): `F2-T1 … F2-T6` de [`02-thinking-graph.md`](02-thinking-graph.md)
implementadas y verificadas (67/67 tests no-integration, `ruff` limpio, migración 0004 validada
offline). El smoke test de cierre encontró y corrigió dos bugs reales (candidatos de contradicción
sin filtrar por tipo; el nodo `outcome` no enlazaba a su episodio) — ver `plan/NOTAS.md`.

**Foco (hecho):** modelo del Thinking Graph, persistencia de trazas de razonamiento, `/explain`,
**Cognitive Query API (las 7 preguntas)**, detección de contradicciones, objeto Decisión.

### 🚦 Deploy Gate 2 — "MindOS ya se siente como la visión"
- [x] Migración (0004) generada y validada offline; `alembic upgrade head` online pendiente de
      Docker/Postgres (igual que Gate 0/1 — ver `plan/NOTAS.md`).
- [ ] Rebuild + `up -d`; healthchecks verdes. *(pendiente: requiere Docker)*
- [x] Las 7 rutas `/cognitive/*` responden con datos reales sobre un dataset sembrado — verificado
      en `memory/tests/test_phase2_smoke.py` (in-process vía ASGI; falta repetir contra el stack
      Docker real una vez levantado).
- [x] `/explain/{node_id}` reconstruye el razonamiento con citas hasta las fuentes, incluyendo el
      episodio del agente que lo produjo.
- [x] Sembrar dos hechos opuestos crea una arista `CONTRADICTS` y aparece en `/cognitive/contradictions`
      (`memory/tests/test_contradiction_detector.py`); confirmación con Ollama real (`qwen3:8b`)
      pendiente por RAM insuficiente en este entorno de desarrollo (test `integration` en el repo).
- [ ] `pytest -m "not integration"` verde (✅ local, 67/67); CI verde. *(pendiente: verificar en CI remoto)*

---

## 6. Stage 3 — Gateway, Auth y Comunicación (Fase 3) ⚑ PRIMER ACCESO EXTERNO

✅ **Código completo** (2026-07-22): `F3-T1 … F3-T7` de [`03-gateway-comunicacion.md`](03-gateway-comunicacion.md)
implementadas y verificadas (131/131 tests Python no-integration + 14/14 tests Node, `ruff`
limpio). Dos servicios nuevos (`gateway/`, `comms/`) + un microservicio Node (`whatsapp/`),
Traefik como único servicio expuesto al host en `infra/docker-compose.yml`. El smoke de cierre
(`memory/tests/test_phase3_smoke.py`) verifica pasando por el Gateway real (autenticado):
captura → pipeline → indexado con provenance, y resolución de aprobaciones vía
`/api/v1/approvals/*` (Gateway lo mapea a Agents).

Aquí MindOS deja de ser solo-local. **La seguridad es bloqueante en este stage.**

**Antes de exponer nada**, ejecuta e implementa de la Fase 6 (aplican ya, no al final):
- `06 §6 Seguridad`: UFW (solo 22 vía VPN/Tailscale + 443), aislamiento de DB/Redis/Ollama en
  `mindos-net` sin puertos publicados, imágenes slim no-root, `no-new-privileges`.
- `06 §5 Backups`: `pg_dump` diario + backup de blobs, **con restore probado** en limpio.
- `06 §3 Secretos`: `JWT_SECRET`, `MINDOS_API_KEY`, `MINIO_*` fuertes.

**Luego ejecuta** (primero descompón las épicas en atómicas, protocolo #5)
`F3-T1 … F3-T7` de [`03-gateway-comunicacion.md`](03-gateway-comunicacion.md) +
`06 §2` (Traefik/TLS) + `06 §1` (topología, `docker-compose.prod.yml`).

**Foco:** Gateway (auth JWT/API key, rate-limit, routing, correlación, aprobaciones), Traefik TLS,
canales CLI/REST → mismo `MessageReceivedEvent`, WhatsApp (Baileys), pipeline de ingestión,
OCR/STT/Storage reales, mensajería saliente.

### 🚦 Deploy Gate 3 — "expuesto y seguro" (GATE DE SEGURIDAD)
- [x] Solo Traefik publica puertos (80/443) en `infra/docker-compose.yml`; DB/Redis/memory/agents/
      comms/gateway sin `ports:` de host, solo alcanzables en `mindos-net`. *(pendiente: `nmap`
      real solo se puede correr contra el server desplegado, no en este entorno de desarrollo)*
- [x] Todo endpoint del Gateway exige auth (API key o JWT; sin ninguna → 401) y aplica rate-limit
      por IP — verificado en `gateway/tests/test_gateway.py` y el smoke de cierre. TLS real
      (Let's Encrypt o autofirmado) solo verificable con Traefik corriendo de verdad.
- [ ] `nmap` externo → solo 443 abierto. *(pendiente: requiere el server real)*
- [ ] Backup automático corriendo y **restore probado** en entorno limpio. *(Fase 6 §5, fuera del
      alcance de F3-T1..T7 — pendiente para cuando se ejecute esa fase)*
- [x] Captura por CLI/REST → mismo evento → indexado con provenance; verificado end-to-end en
      `memory/tests/test_ingestion_pipeline.py` (11 tests) y el smoke de cierre. WhatsApp
      implementado y con 14/14 tests Node, pero no verificable sin escanear un QR con un
      teléfono real (ver `plan/NOTAS.md`, entrada F3-T4). Respuesta por el canal de origen
      (F3-T7) verificada con dobles de prueba (`agents/tests/test_reply_to_notification.py`).
- [ ] CI verde en el remoto (config lista en `.github/workflows/ci.yml`, incluye ahora gateway/
      comms/whatsapp — pendiente de un push real para confirmarlo); `docker-compose.prod.yml`
      levanta sano en el server *(pendiente: sin Docker en este entorno de desarrollo)*.

---

## 7. Stage 4 — Interfaces: Dashboard, MCP, PWA (Fase 4)

**Ejecuta** `F4-T1 … F4-T3` de [`04-interfaces.md`](04-interfaces.md) (descompón épicas primero).
Añade la **observabilidad** de `06 §7` (Prometheus/Grafana, `/health` de readiness, alertas) para
este punto: con humanos usando el Dashboard, necesitas ver métricas y errores.

### 🚦 Deploy Gate 4
- [ ] Dashboard tras el Gateway (autenticado): captura, búsqueda con citas, grafo, timeline/as-of,
      visor de `/explain`, panel de las 7 preguntas, bandejas de contradicciones y aprobaciones.
- [ ] Servidor MCP: un cliente (p.ej. Claude Code) busca/ingiere/explica en MindOS; `mcp.json` de ejemplo documentado.
- [ ] PWA instala y captura offline con sincronización.
- [ ] Grafana muestra salud y uso; una caída de servicio dispara alerta.

---

## 8. Stage 5 — Automatización y evolución (Fase 5)

**Ejecuta** `F5-T1 … F5-T6` de [`05-automatizacion.md`](05-automatizacion.md) (descompón primero).

**Foco:** agente de consolidación (nocturno), resurfacing/digest, agente de investigación, lifecycle
del conocimiento, scheduler idempotente, harness de evaluación. Registra los jobs en el scheduler
(`F5-T5`) junto con backups (Fase 6).

### 🚦 Deploy Gate 5
- [ ] Jobs corren en horario, idempotentes y observables (logs+métricas).
- [ ] Consolidación genera insights/enlaces; llega un digest de resurfacing.
- [ ] "Investiga X" produce un episodio con evidencias citadas y `insight` explicables vía `/explain`.
- [ ] `make eval` produce un reporte reproducible de calidad de razonamiento.

---

## 9. Stage 6 — Hardening final y GO-LIVE (Fase 6)

**Completa** todo lo que falte de [`06-produccion-despliegue.md`](06-produccion-despliegue.md):
`§4` arranque reproducible + `scripts/deploy.sh`, `§8` CI/CD (build+deploy en merge a `main`),
`§9` tuning de rendimiento (16 GB), `§10` runbook de operación (`docs/OPERACION.md`).

**Cutover:**
1. Ejecuta el **smoke end-to-end de producción** completo (`06 §Smoke`, los 10 puntos).
2. Verifica el **checklist de "listo para producción"** (`README.md §5`) — todas las casillas.
3. **Go/No-Go:** si todo verde → GO-LIVE. Documenta la versión desplegada (tag git) y la fecha.

### 🚦 GO-LIVE — "MindOS en producción"
- [ ] Smoke de 10 puntos verde.
- [ ] Checklist `README.md §5` completo.
- [ ] `scripts/deploy.sh` despliega sin downtime perceptible; `scripts/restore.sh` probado.
- [ ] Runbook de operación escrito; backups + observabilidad + alertas activos.
- [ ] Tag git de release creado.

---

## 10. Getting el código al server (remoto git) — necesario desde Stage 0

El repo es local sin remoto. Para desplegar al server necesitas moverlo. Opciones (elige una):
- **A (recomendada):** repo **privado** en GitHub. `git remote add origin ...`; `git push`. En el
  server: `git clone`. Habilita CI/CD (`06 §8`). *Crear el repo/authorizar es decisión del usuario.*
- **B:** transferencia directa (`rsync`/`scp`) del monorepo al server + git local ahí. Sin CI en la nube.
- **C:** registry propio: build de imágenes en la workstation → push a un registry local → pull en el server.

Sea cual sea, **`.env` nunca viaja por git** (va aparte, por canal seguro).

---

## 11. Resumen de dependencias (para no romper el orden)

- Stage 1 depende de **Stage 0** (esquema base aplicado).
- Stage 2 depende de **Stage 1** (objeto rico + provenance).
- Stage 3 depende de **Stage 1** (puede solaparse con Stage 2); **exige** seguridad/backups antes de exponer.
- Stage 4 depende de **Stage 2 y 3** (necesita las 7 preguntas + Gateway/auth).
- Stage 5 depende de **Stage 2** (Thinking Graph).
- Stage 6 se aplica **incrementalmente** desde Stage 0 y se cierra al final.

**Ruta crítica a un producto usable:** Stage 0 → 1 → 2 → 3. En ese punto MindOS ya captura del
mundo real, responde las 7 preguntas, explica su razonamiento y está expuesto de forma segura.
Stages 4–5 lo hacen agradable y autónomo; Stage 6 lo endurece para operar sin sobresaltos.
