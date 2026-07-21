# Fase 6 — Producción y despliegue

**Objetivo:** operar MindOS de forma **segura, respaldada y observable** en el **servidor Ubuntu
24/7** (i7-1065G7, 16 GB, NVMe 512 GB). Este playbook se aplica de forma **incremental**: usa las
secciones de Docker/CI desde la Fase 0; las de seguridad/backups/observabilidad antes de exponerlo.

---

## §1 · Topología de despliegue

- **Server Ubuntu (24/7):** Postgres+pgvector, Redis, Memory, Agents, Comms, Gateway, MCP, Dashboard,
  pipeline de ingestión, scheduler, Traefik, Ollama (`qwen3:8b` + `nomic-embed-text`), MinIO.
- **Workstation (Windows, on-demand):** Ollama con modelos pesados (`qwen3-coder:30b`,
  `qwen2.5-coder:14b`) accesible por LAN para el agente de investigación. Apunta
  `OLLAMA_URL_WORKSTATION` a su IP; el server la usa solo para el rol `research`.
- **Restricción de RAM (16 GB en el server):** define `mem_limit` por servicio en compose.
  Presupuesto sugerido: Postgres 2 GB, Redis 512 MB, Ollama ~7 GB (qwen3:8b Q4 + embed), servicios
  Python ~500 MB c/u, Dashboard/Traefik ~300 MB. **No** cargar modelos ≥14B en el server.

## §2 · `docker-compose.prod.yml` (stack completo)

Crea `infra/docker-compose.prod.yml` extendiendo el base con **todos** los servicios. Requisitos:
- Cada servicio: `restart: unless-stopped`, `healthcheck`, `mem_limit`, logging con rotación
  (`json-file` `max-size=10m max-file=3`), red `mindos-net` interna.
- **Solo Traefik expone puertos al host** (80/443). Los demás publican **solo** en la red interna.
- `migrate` one-shot corre `alembic upgrade head` y termina; `memory` depende de él.
- Volúmenes con nombre: `postgres_data`, `redis_data`, `minio_data`, `whatsapp_session`,
  `ollama_models` (si Ollama va en contenedor; si va en host, omitir).
- Variables por `.env` (NO en el compose). Provee `.env.example` con todas las claves y sin valores
  secretos.
- **DoD:** `docker compose -f infra/docker-compose.prod.yml --env-file .env up -d` deja todo healthy
  y solo 443 accesible desde fuera.

## §3 · Configuración y secretos

- `.env` fuera de git (ya en `.gitignore`); `.env.example` documentado en git.
- Genera secretos fuertes: `POSTGRES_PASSWORD`, `JWT_SECRET`, `MINDOS_API_KEY`, `MINIO_*`.
- Para producción real, migra secretos sensibles a **Docker secrets** o SOPS/age (cifrado en reposo
  del propio `.env`).
- Un único `mindos_common.config` centraliza la lectura; ningún servicio lee `os.getenv` disperso.
- **DoD:** arrancar en una máquina limpia solo requiere copiar `.env` y `docker compose up`.

## §4 · Migraciones y arranque reproducible

- Alembic es la **única** vía de cambio de esquema (nada de `create_all` en prod).
- El deploy corre `alembic upgrade head` (servicio `migrate`) antes de servir tráfico.
- Script `scripts/deploy.sh`: `git pull` → `docker compose build` → `up -d migrate` (espera exit 0)
  → `up -d` resto → healthcheck loop → reporte.
- **DoD:** partiendo de DB vacía, un solo comando deja el sistema operativo con esquema al día.

## §5 · Backups y recuperación (probada)

- **Postgres:** `pg_dump` diario (cron/`scheduler`) a `backups/pg/`, retención 14 días + 1 mensual;
  comprimido. Considera `pgBackRest`/WAL-archiving para PITR si el dato lo amerita.
- **Blobs (MinIO/FS):** `restic`/`rclone` a disco externo o almacenamiento local secundario, cifrado.
- **Redis:** AOF ya activo; respalda el `appendonly` periódicamente (el estado del bus es efímero,
  pero los consumer-groups importan).
- **Restore drill (OBLIGATORIO):** documenta y **prueba** el restore en un entorno limpio
  (`scripts/restore.sh`). Un backup no probado no es un backup.
- **DoD:** ejecutar el restore en una VM/carpeta limpia reconstruye datos y blobs; smoke-test verde.

## §6 · Seguridad (antes de exponer nada)

- **UFW/firewall:** solo 22 (SSH, idealmente por VPN/Tailscale) y 443. Todo lo demás cerrado.
- **TLS:** Traefik con Let's Encrypt (si hay dominio) o cert propio en LAN.
- **Auth:** Gateway obliga JWT/API key en todo endpoint; sin auth → 401. Rate-limit activo.
- **Aislamiento:** DB/Redis/Ollama sin puertos publicados al host; solo `mindos-net`.
- **Superficie mínima:** imágenes `slim`, usuario no-root en contenedores, `read_only` donde se pueda,
  `no-new-privileges`.
- **Actualizaciones:** `unattended-upgrades` en el host; rebuild periódico de imágenes base.
- **Secretos de WhatsApp** en volumen cifrado; nunca en logs.
- **Privacidad (principio del proyecto):** cifrado en reposo del volumen de datos (LUKS o cifrado del
  `.env`/backups); ningún dato sale a la nube salvo que el usuario lo habilite explícitamente.
- **DoD:** un escaneo de puertos externo solo ve 443; ninguna ruta responde sin credencial.

## §7 · Observabilidad

- **Logs:** ya estructurados (structlog+correlación). Añade agregación ligera (Loki/Promtail o
  `docker logs` + rotación) y un panel de errores.
- **Métricas:** instrumenta FastAPI con **prometheus-client** (latencia, throughput, errores por
  endpoint; profundidad de streams Redis; tiempos de LLM/embeddings). Prometheus + Grafana en compose
  (o Grafana Cloud si se acepta). Dashboards: salud del stack, uso de LLM, tasa de ingesta.
- **Trazas:** OpenTelemetry en Gateway→servicios→DB, exportando a Tempo/Jaeger (opcional pero
  recomendado); el `correlation_id` ya permite correlacionar sin esto.
- **Healthchecks:** `/health` real (DB ping, Redis ping, Ollama tags) en cada servicio; Traefik y
  compose los usan.
- **Alertas:** reglas mínimas (servicio caído, DB sin espacio, cola de eventos creciendo, LLM
  fallando) → notificación al canal del usuario.
- **DoD:** Grafana muestra salud y uso; un servicio caído se detecta y alerta.

## §8 · CI/CD

- **CI (GitHub Actions):** en cada push → `ruff check` + `pytest -m "not integration"` + `docker build`
  de todas las imágenes. En tags → build + push a un registry (GHCR o local).
- **CD (server local):** opción A (simple) `scripts/deploy.sh` ejecutado por SSH/manualmente; opción B
  **runner self-hosted** en el server que hace pull+deploy en merge a `main`. Empieza por A.
- **Estrategia de branches:** `main` protegido (CI verde obligatorio), feature branches por tarea del plan.
- **DoD:** merge a `main` con CI verde produce imágenes; `deploy.sh` las pone en el server sin downtime
  perceptible (arranque escalonado + healthchecks).

## §9 · Rendimiento y capacidad (16 GB)

- Pool de conexiones Postgres acotado; `work_mem`/`shared_buffers` ajustados al server.
- Índices: HNSW en embeddings (F0-T4), índices en `relations(source_id) WHERE valid_to IS NULL`,
  en `knowledge_node_versions(node_id, version)` y en `created_at` (timeline/temporal).
- LLM: **un modelo cargado** en el server (`OLLAMA_KEEP_ALIVE` prudente); cola las peticiones para no
  saturar RAM. Investigación pesada → workstation.
- Embeddings en **batch** cuando el pipeline procese lotes.
- **DoD:** ingesta y búsqueda responden en tiempos aceptables bajo carga típica de un usuario; sin OOM.

## §10 · Runbook de operación

Documenta en `docs/OPERACION.md`:
- Arrancar/parar: `docker compose ... up -d` / `down`.
- Ver estado/logs: `docker compose ps`, `docker compose logs -f <svc>`.
- Actualizar: `scripts/deploy.sh`.
- Backup/restore: `scripts/backup.sh` / `scripts/restore.sh`.
- Rotar secretos; renovar TLS; migraciones manuales; recuperar sesión de WhatsApp.
- Qué hacer si: DB llena, Ollama caído, stream atascado, servicio en crash-loop.

---

## §Smoke · Prueba end-to-end de producción

Con el stack prod arriba, todo debe pasar:
1. `POST /api/v1/comms/inbound` (vía Gateway, autenticado) con una nota de texto → 200.
2. La nota aparece en `/search` con cita y `source`.
3. Enviar un **PDF** por WhatsApp → blob en MinIO + nodo indexado + evento (verifica en logs/DB).
4. Preguntar una de las **7 preguntas** por Dashboard → respuesta con datos reales.
5. Un **agente** responde una pregunta y `/explain` muestra su razonamiento con citas.
6. Sembrar dos hechos contradictorios → aparece en la **bandeja de contradicciones**.
7. Correr **consolidación** manualmente → genera insights/enlaces; llega un **digest**.
8. Cortar un servicio → **alerta**; `deploy.sh` lo restaura.
9. Ejecutar `restore.sh` en carpeta limpia → datos y blobs reconstruidos.
10. `nmap` externo → solo 443 abierto; sin token → 401 en todo.

Cuando el smoke pasa completo y el checklist de `README.md §5` está en verde: **MindOS está en
producción.**
