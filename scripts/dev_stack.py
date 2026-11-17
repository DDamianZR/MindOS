"""
Stack local de desarrollo de MindOS, sin Docker (Fase 7).

    python scripts/dev_stack.py            # memory + agents + gateway
    python scripts/dev_stack.py agents     # un solo servicio (lo usa .claude/launch.json)
    python scripts/dev_stack.py seed       # carga notas de ejemplo en la memoria en marcha

Todo corre en memoria (sin Postgres ni Redis) y con embeddings simulados, así que arranca en
segundos y no deja nada en disco. Sirve para trabajar la interfaz y los agentes; la verificación
contra Postgres/Redis reales sigue siendo `docker compose` (ver plan/06).

El Dashboard se levanta aparte: `npm --prefix dashboard run dev`, y se entra con las
credenciales de desarrollo de abajo. El asistente usa Claude si `ANTHROPIC_API_KEY` está en el
entorno o en el `.env` de la raíz; si no, responde en modo demostración.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Solo para desarrollo local: estos valores nunca deben llegar a un `.env` de producción.
DEV_USERNAME = "admin"
DEV_PASSWORD = "mindos-dev"
DEV_API_KEY = "dev-only-api-key"
DEV_JWT_SECRET = "dev-only-jwt-secret-no-usar-fuera-de-esta-maquina"

PORTS = {"gateway": 8000, "memory": 8001, "agents": 8002}
MODULES = {
    "gateway": "gateway.src.main:app",
    "memory": "memory.src.main:app",
    "agents": "agents.src.main:app",
}


def service_env(service: str) -> dict[str, str]:
    env = dict(os.environ)
    # Los paquetes compartidos se toman de ESTE checkout (importa en worktrees, donde la
    # instalación editable apunta al checkout principal).
    extra_paths = [str(ROOT), str(ROOT / "schemas"), str(ROOT / "common")]
    env["PYTHONPATH"] = os.pathsep.join(extra_paths + [p for p in [env.get("PYTHONPATH")] if p])
    env.setdefault("MINDOS_ENV", "development")
    env.update({
        "MEMORY_URL": f"http://localhost:{PORTS['memory']}",
        "AGENTS_URL": f"http://localhost:{PORTS['agents']}",
        "COMMS_URL": "http://localhost:8003",
    })

    if service == "memory":
        env.update({
            "DATABASE_TYPE": "in_memory", "STORAGE_TYPE": "in_memory",
            "EMBEDDING_PROVIDER": "mock", "LLM_PROVIDER": "mock",
            "OCR_PROVIDER": "mock", "STT_PROVIDER": "mock",
        })
    elif service == "gateway":
        from gateway.src.application.services.security import hash_password

        env.update({
            "RATE_LIMITER_TYPE": "in_memory", "DASHBOARD_URL": "http://localhost:3000",
            "MINDOS_API_KEY": DEV_API_KEY, "JWT_SECRET": DEV_JWT_SECRET,
            "MINDOS_ADMIN_USERNAME": DEV_USERNAME,
            "MINDOS_ADMIN_PASSWORD_HASH": hash_password(DEV_PASSWORD),
        })
    return env


def uvicorn_command(service: str) -> list[str]:
    return [
        sys.executable, "-m", "uvicorn", MODULES[service],
        "--host", "127.0.0.1", "--port", str(PORTS[service]),
    ]


def run_one(service: str) -> int:
    return subprocess.call(uvicorn_command(service), cwd=ROOT, env=service_env(service))


def run_all() -> int:
    processes = [
        subprocess.Popen(uvicorn_command(service), cwd=ROOT, env=service_env(service))
        for service in ("memory", "agents", "gateway")
    ]
    print(
        f"\nMindOS local: Gateway en http://localhost:{PORTS['gateway']}\n"
        f"Entra al Dashboard con usuario '{DEV_USERNAME}' y contraseña '{DEV_PASSWORD}'.\n"
        "Ctrl+C detiene los tres servicios.\n"
    )
    try:
        while all(p.poll() is None for p in processes):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in processes:
            p.terminate()
    return 0


SEED_NOTES = [
    ("decision", "Decisión: PostgreSQL con pgvector como único motor", 0.9,
     "Elegí PostgreSQL 16 con pgvector para guardar conocimiento, versiones, relaciones y vectores "
     "en un solo motor. Descarté Neo4j y una base vectorial aparte porque el servidor tiene 16 GB "
     "y quiero operar una sola base. El grafo se resuelve con tablas y CTE recursivas."),
    ("decision", "Decisión: Claude Sonnet 5.5 para el asistente personal", 0.9,
     "El asistente conversacional usa la API de Claude con el modelo Sonnet 5.5. Los modelos "
     "locales de 8B no sostenían bien el uso de herramientas en varios pasos y ocupaban la RAM "
     "del servidor. Ollama se queda solo para los embeddings (nomic-embed-text, 768 dimensiones)."),
    ("learning", "Aprendizaje: verificar en el navegador encuentra lo que los tests no", 0.7,
     "Al conectar el Dashboard al Gateway real aparecieron tres bugs de backend que ningún test "
     "había ejercitado: /neighbors solo seguía aristas salientes, el Gateway no ruteaba thinking "
     "ni cognitive, y el slider as-of perdía precisión de microsegundos."),
    ("idea", "Idea: digest semanal de lo que dejé a medias", 0.6,
     "Un resumen cada domingo con las preguntas abiertas, las hipótesis sin evidencia y las "
     "decisiones que llevan más de un mes sin revisarse. Llegaría por WhatsApp."),
    ("note", "Hardware del servidor de casa", 0.5,
     "Servidor Ubuntu con i7-1065G7 y 16 GB de RAM, sin GPU dedicada, encendido 24/7. La estación "
     "de trabajo es una Ryzen 9 8940HX y se usa bajo demanda por la red local."),
    ("hypothesis", "Hipótesis: bge-m3 recupera mejor que nomic-embed-text en español", 0.6,
     "Sospecho que bge-m3 (1024 dimensiones, multilingüe) daría mejor recuperación para mis notas "
     "en español que nomic-embed-text. Falta medirlo con el harness de evaluación de la Fase 5."),
    ("task", "Pendiente: probar el restore del backup en limpio", 0.8,
     "Antes de exponer el Gateway a internet falta ejecutar un restore completo de pg_dump y de "
     "los blobs en una máquina limpia. Es un requisito del gate de seguridad del Stage 3."),
    ("fact", "Solo Traefik publica puertos en producción", 0.7,
     "En infra/docker-compose.yml el único servicio con puertos al host es Traefik (80 y 443). "
     "Postgres, Redis, Memory, Agents, Comms y el Gateway solo son alcanzables dentro de mindos-net."),
]


def seed() -> int:
    import httpx

    base_url = f"http://localhost:{PORTS['memory']}"
    with httpx.Client(timeout=15.0) as client:
        for object_type, title, importance, content in SEED_NOTES:
            response = client.post(f"{base_url}/api/v1/memory/ingest", json={
                "object_type": object_type, "title": title, "content": content,
                "author": "dev-seed", "importance": importance, "on_duplicate": "force_new",
            })
            response.raise_for_status()
            print(f"  + {title}")
    print(f"\n{len(SEED_NOTES)} notas de ejemplo cargadas en la memoria local.")
    return 0


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target == "all":
        return run_all()
    if target == "seed":
        return seed()
    if target in MODULES:
        return run_one(target)
    print(f"Uso: python scripts/dev_stack.py [{' | '.join(MODULES)} | seed]")
    return 2


if __name__ == "__main__":
    sys.exit(main())
