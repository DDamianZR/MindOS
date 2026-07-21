# Fase 0 — Fundaciones: kernel correcto, persistente y desplegable

**Objetivo:** eliminar los bugs que invalidan la persistencia, volver el sistema *event-driven*
de verdad, conectar embeddings reales, y dejar el stack **arrancable con Docker**. Sin esto,
todo lo demás se construye sobre arena.

**Precondición:** Ollama corriendo con `nomic-embed-text` y `qwen3:8b` disponibles
(`curl http://localhost:11434/api/tags`). Postgres/Redis se levantan con `infra/docker-compose.yml`.

**Duración estimada:** ~1 semana. **Al terminar:** `pytest` verde en todos los módulos,
modo `postgres` funcional, ingesta emite eventos, `docker compose up` levanta memory+agents.

---

## F0-T1 · Consolidar a monorepo

**Por qué:** hay 9 repos git anidados, la mayoría vacíos y ninguno con commits. Un monorepo
simplifica build, test, CI y deploy.

**Pasos:**
1. Verifica que ningún submódulo tiene commits que perder:
   ```bash
   for d in schemas common memory agents architecture docs gateway whatsapp dashboard mcp infra experiments playground; do
     echo "== $d =="; git -C "$d" log --oneline -1 2>/dev/null || echo "sin git";
   done
   ```
   Todos deben devolver vacío (sin commits). Si alguno tuviera commits, PARA y anótalo en `plan/NOTAS.md`.
2. Elimina los `.git` anidados (conserva los archivos de trabajo):
   ```bash
   find . -mindepth 2 -type d -name .git -not -path './.git/*' -print -exec rm -rf {} + 2>/dev/null
   ```
3. Inicializa el monorepo en la raíz y crea `.gitignore`:
   ```
   __pycache__/  *.pyc  .venv/  venv/  .env  *.egg-info/  .pytest_cache/  .ruff_cache/
   node_modules/  .next/  dist/  build/  *.log  postgres_data/  redis_data/  minio_data/
   ```
4. Borra el archivo basura `2.0.0` de la raíz (es un log de pip suelto).
5. Crea `pyproject.toml` raíz declarando un workspace/monorepo con dependencias comunes y
   apuntando a los paquetes locales (`schemas`, `common`) como editables. Mantén los
   `requirements.txt` por servicio para las imágenes Docker.
6. `git init && git add -A && git commit -m "chore: consolidar MindOS en monorepo"`.

**DoD:** `git log --oneline` muestra 1 commit en la raíz; `find . -name .git -type d` solo
devuelve `./.git`; `python -m pytest` (raíz) sigue verde.

---

## F0-T2 · Utilidad `uuid7` y erradicar `hash()` como generador de IDs

**Por qué:** IDs con `hash()` son irreproducibles (PYTHONHASHSEED) y colisionan. La visión pide UUIDv7.

**Pasos:**
1. En `common/mindos_common/ids.py` crea:
   ```python
   import uuid
   def new_id() -> uuid.UUID:
       """UUIDv7: ordenable temporalmente, único. Requiere Python 3.12+."""
       return uuid.uuid7()
   ```
2. Reemplaza **todos** los usos de generación de ID:
   - `memory/src/main.py`: `uuid.uuid4()` → `new_id()`.
   - `memory/src/infrastructure/database/repositories.py:46`: elimina
     `UUID(int=hash(f"{node_id}-{version}") & ...)`; usa `new_id()` para el `id` de la versión.
   - `common/mindos_common/event_bus.py:37`: elimina `UUID(int=hash(...))`; usa `new_id()`.
   - `agents/src/main.py`: `uuid.uuid4()` → `new_id()`.
3. Busca residuos: `grep -rn "hash(" --include=*.py . | grep -i uuid` → debe quedar vacío.

**DoD:** `grep -rn "UUID(int=hash" --include=*.py .` no devuelve nada; tests verdes.

---

## F0-T3 · Corregir lineaje de versiones y `created_at` en ingest

**Por qué:** `parent_version_id` apunta al `node_id` (nodo) en vez de a la **versión previa**;
y el `created_at` devuelto es el de la versión anterior. Rompe la reconstrucción histórica.

**Pasos (en `memory/src/main.py`, endpoint `ingest_knowledge`):**
1. `save_node_version` debe recibir y devolver el **id de versión** generado. Cambia el puerto
   `DatabasePort.save_node_version` y sus 2 implementaciones (Pg + InMemory) para:
   - Aceptar `version_id: UUID` (generado con `new_id()` en el caller).
   - `get_latest_node_version` debe devolver también la clave `version_id` (id de la fila de versión),
     no solo `node_id`.
2. En el caller: `parent_version_id = latest_ver["version_id"] if latest_ver else None`.
3. Tras guardar, **relee** la versión recién creada para devolver su `created_at` real
   (o genera el timestamp en el caller y pásalo explícito a ambos adaptadores para consistencia).
4. Añade un test `memory/tests/test_versioning.py`: ingesta v1 → ingesta v2 del mismo `node_id` →
   `get_node_versions` devuelve 2 filas; la v2 tiene `parent_version_id == id(v1)`.

**DoD:** el nuevo test pasa; el `parent_version_id` de v2 == id de la fila v1.

---

## F0-T4 · Alembic + pgvector + dimensión de embedding correcta

**Por qué:** hoy `DATABASE_TYPE=postgres` **no arranca** (sin tablas, sin extensión, sin índice).
Además `Vector(384)` no coincide con `nomic-embed-text` (768).

**Pasos:**
1. Añade `alembic` a `memory/requirements.txt`. `cd memory && alembic init alembic`.
2. Configura `alembic/env.py` para usar `settings.DATABASE_URL` (async) y
   `target_metadata = Base.metadata` (de `models.py`).
3. En `models.py`: cambia `Vector(384)` → `Vector(settings.EMBEDDING_DIM)` con `EMBEDDING_DIM=768`
   por defecto (config en `F0-T5`). Si Alembic no puede leer settings, deja `Vector(768)` y un
   comentario `# = EMBEDDING_DIM`.
4. Primera migración: `alembic revision --autogenerate -m "initial schema"`. Edítala para incluir
   al inicio:
   ```python
   op.execute("CREATE EXTENSION IF NOT EXISTS vector")
   ```
   y al final, un índice vectorial:
   ```python
   op.execute("CREATE INDEX IF NOT EXISTS ix_versions_embedding ON knowledge_node_versions "
              "USING hnsw (embedding vector_cosine_ops)")
   ```
   y un índice para caminatas de grafo: `CREATE INDEX ON relations (source_id) WHERE valid_to IS NULL`.
5. En `memory/src/main.py` lifespan (modo postgres): ejecuta `alembic upgrade head` o, para dev,
   `Base.metadata.create_all` + `CREATE EXTENSION`. Documenta el comando en el README de memory.
6. Añade a `infra/docker-compose.yml` un servicio `migrate` (one-shot) que corre `alembic upgrade head`
   antes de que arranque `memory` (o hazlo en el entrypoint del contenedor memory).

**DoD:** con Postgres levantado y `DATABASE_TYPE=postgres`, `alembic upgrade head` crea las tablas,
la extensión `vector` y el índice HNSW; `curl POST /api/v1/memory/ingest` responde 201 y persiste.

---

## F0-T5 · Config central + adaptador de embeddings real (Ollama)

**Por qué:** solo existe `MockEmbedding`. El core RAG necesita embeddings reales; y la asignación
de modelos por rol debe ser configurable.

**Pasos:**
1. En `common/mindos_common/config.py` crea un `BaseSettings` compartido con las variables del
   README §2 (URLs de Ollama por host, modelos por rol, `EMBEDDING_MODEL`, `EMBEDDING_DIM`).
   Los `Settings` por servicio heredan de este.
2. Crea `memory/src/infrastructure/adapters/ollama_embedding.py` implementando `EmbeddingPort`:
   ```python
   import httpx
   from memory.src.application.ports.embedding import EmbeddingPort
   class OllamaEmbedding(EmbeddingPort):
       def __init__(self, base_url: str, model: str):
           self.base_url, self.model = base_url, model
           self.client = httpx.AsyncClient(timeout=60.0)
       async def embed_query(self, text: str) -> list[float]:
           r = await self.client.post(f"{self.base_url}/api/embeddings",
                                      json={"model": self.model, "prompt": text})
           r.raise_for_status()
           return r.json()["embedding"]
       async def embed_documents(self, texts):  # batch simple secuencial (o usa /api/embed)
           return [await self.embed_query(t) for t in texts]
   ```
3. En `memory/src/main.py`: inyecta `OllamaEmbedding` cuando `MINDOS_ENV != test` (mock en tests).
   Reemplaza el `mock_embedding` global por selección vía dependencia.
4. Añade un test de integración `@pytest.mark.integration` (skippeable) que verifica dim==768
   contra Ollama; y un test unitario con embedding mockeado por `respx`/monkeypatch.

**DoD:** ingesta real genera y guarda un vector de 768 dims; `search` devuelve resultados
ordenados por similitud real (ver `F0-T7`); tests unitarios verdes sin depender de Ollama.

---

## F0-T6 · Hacer la ingesta *event-driven* (emitir eventos + event_log)

**Por qué:** el principio rector es event-driven, pero la ingesta no publica nada ni escribe
`knowledge_event_log`. El Event Bus está sin cablear.

**Pasos:**
1. En `memory/src/main.py`, instancia `RedisEventBus(settings.REDIS_URL)` en el lifespan.
2. Tras un ingest/update exitoso:
   - `await db_repo.save_event_log(new_id(), "com.mindos.memory.knowledge.created", payload)`
     (o `.updated` si `version > 1`), dentro de la misma transacción.
   - `await event_bus.publish("mindos.memory", event_type, KnowledgeCreatedEventData(...), correlation_id)`.
3. Igual para `save_relation` → `RelationCreatedEventData`, `delete_relation` → `RelationDeletedEventData`.
4. Propaga `correlation_id`: acéptalo como header `X-Correlation-Id` en los endpoints; si falta,
   genera con `new_id()` y ponlo con `set_correlation_id`.
5. Test: un consumidor de prueba suscrito al stream recibe el evento tras un ingest (usa
   `fakeredis` o un Redis de test); y `knowledge_event_log` tiene 1 fila.

**DoD:** tras `POST /ingest`, existe fila en `knowledge_event_log` y un mensaje en el stream
`mindos.memory` con el `correlation_id` correcto.

---

## F0-T7 · Score de similitud real en pgvector

**Por qué:** `PgVectorStoreRepository.search` devuelve `score=1.0` fijo; se pierde el ranking.

**Pasos:** en `pgvector.py`, selecciona también la distancia y conviértela a similitud:
```python
dist = DbObjectVersion.embedding.cosine_distance(query_embedding)
stmt = (select(DbObjectVersion, dist.label("distance"))
        .where(DbObjectVersion.embedding.isnot(None))
        .order_by(dist.asc()).limit(limit))
# score = 1 - distance  (coseno)
```
Mapea `score=1.0 - row.distance`. Ajusta el mapeo de filas (ahora son tuplas `(version, distance)`).

**DoD:** una búsqueda con 3 nodos de distinta similitud devuelve `score` descendente y coherente
(el más parecido primero, score más alto).

---

## F0-T8 · Tope de reintentos en el grafo del agente

**Por qué:** `_should_continue` puede alternar replan↔execute indefinidamente si el Reviewer
nunca aprueba.

**Pasos:**
1. Añade `retries: int` y `max_retries: int` (default 3) a `AgentState`.
2. En `_plan_node` (replan) incrementa `retries`. En `_should_continue`, si `retries >= max_retries`
   devuelve `"end"` con un `final_output` de fallo controlado y `error` explicativo.
3. Test: un Reviewer que siempre rechaza termina el grafo en `max_retries` sin colgarse.

**DoD:** el test de "reviewer que siempre rechaza" termina en ≤ `max_retries` iteraciones.

---

## F0-T9 · Dockerizar y orquestar el stack

**Por qué:** hoy el compose solo levanta Postgres+Redis; los servicios no están containerizados.

**Pasos:**
1. `Dockerfile` en `memory/` y `agents/` (multi-stage, base `python:3.12-slim`), instalando
   `-e ../schemas -e ../common` + su `requirements.txt`. Copia el contexto del monorepo necesario.
2. Extiende `infra/docker-compose.yml` (quita `version: '3.8'`, obsoleto) con servicios:
   - `memory` (puerto 8001, `DATABASE_TYPE=postgres`, depende de `postgres` healthy + `migrate`).
   - `agents` (puerto 8002, `MEMORY_URL=http://memory:8001`, `OLLAMA_URL` al host).
   - `migrate` (one-shot Alembic).
   - Ollama: por defecto usar el del **host** (`host.docker.internal` / IP LAN); documenta cómo
     apuntar a un Ollama containerizado opcional.
   - Healthchecks HTTP (`/health`) en memory y agents (añade endpoint `/health` que verifique DB/Redis).
3. Red bridge `mindos-net`; variables por `.env` (crea `.env.example`).

**DoD:** `docker compose -f infra/docker-compose.yml up -d` deja `postgres`, `redis`, `memory`,
`agents` en estado healthy; `curl localhost:8001/health` y `localhost:8002/health` responden 200.

---

## F0-T10 · Calidad continua: ruff + pytest + CI

**Pasos:**
1. Unifica `ruff.toml` en la raíz (ya existe uno); asegúrate de que cubre todos los paquetes.
2. `pytest.ini`/`pyproject` con `asyncio_mode = auto` y marcadores (`integration`).
3. `.github/workflows/ci.yml`: matriz Python 3.12; instala paquetes editables; corre
   `ruff check .` y `pytest -m "not integration"`; build de imágenes Docker (sin push).
4. `pre-commit` opcional (ruff format + ruff check).

**DoD:** `ruff check .` sin errores; `pytest -m "not integration"` verde; el workflow corre en push.

---

## Cierre de Fase 0 — verificación integral

Ejecuta y confirma todo verde antes de pasar a Fase 1:
```bash
ruff check .
python -m pytest -m "not integration"
docker compose -f infra/docker-compose.yml up -d
curl -s localhost:8001/health && curl -s localhost:8002/health
# ingesta real + búsqueda + historial
curl -sX POST localhost:8001/api/v1/memory/ingest -H 'content-type: application/json' \
  -d '{"entity_type":"note","title":"Traefik","content":"Puerto 443 configurado","author":"damian"}'
curl -sX POST "localhost:8001/api/v1/memory/search?query=puerto%20traefik&limit=3"
```
Marca aquí cuando esté hecho:
- [ ] F0-T1 monorepo · [ ] F0-T2 uuid7 · [ ] F0-T3 lineaje · [ ] F0-T4 Alembic/pgvector
- [ ] F0-T5 embeddings reales · [ ] F0-T6 eventos · [ ] F0-T7 score · [ ] F0-T8 retries
- [ ] F0-T9 Docker · [ ] F0-T10 CI
