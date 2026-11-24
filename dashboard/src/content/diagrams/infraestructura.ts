import type { DiagramCategory } from "./types";

// Lo dibujado es lo que el repo hace hoy. El plan de producción pide más
// (copias, métricas, script de despliegue); eso se dice en la descripción y no se pinta.
export const infraestructura: DiagramCategory = {
  id: "6",
  slug: "infraestructura",
  title: "Infraestructura y DevOps",
  summary:
    "Muestra dónde corre MindOS en casa, cómo se conectan sus máquinas y qué hay hoy para construirlo, vigilarlo y no perder datos.",
  diagrams: [
    {
      id: "6.1",
      slug: "diagrama-de-infraestructura",
      title: "Diagrama de infraestructura",
      status: "generated",
      description:
        "Reúne el servidor de casa, la estación donde corre el Dashboard y las salidas reales, Claude y WhatsApp. El Dashboard no es un contenedor: en el stack entra por Traefik, y los modelos grandes de la estación no están cableados porque solo hay una dirección de Ollama.",
      mermaid: `flowchart TB
  estacion["Estación de trabajo, Ryzen 9 8940HX<br/>Dashboard con npm, puerto 3000<br/>por defecto apunta a localhost:8000"]
  subgraph servidor["Servidor Ubuntu 24/7, i7-1065G7, 16 GB, sin GPU"]
    ollama["Ollama en el host, puerto 11434<br/>qwen3:8b y nomic-embed-text"]
    traefik["Traefik v3.1<br/>únicos puertos del host, 80 y 443"]
    servicios["Contenedores del proyecto mindos<br/>gateway, memory, agents, comms,<br/>whatsapp, mcp, postgres, redis, migrate"]
  end
  claude["API de Claude<br/>api.anthropic.com"]
  wasrv["Servidores de WhatsApp"]

  estacion -->|"en el stack, el Gateway solo se ve por el 443"| traefik
  traefik --> servicios
  servicios -->|"host.docker.internal:11434"| ollama
  servicios -->|"saliente, si hay clave"| claude
  servicios -->|"Baileys, solo saliente"| wasrv`,
      basedOn: [
        "infra/docker-compose.yml",
        "scripts/dev_stack.py",
        "dashboard/src/lib/api-client.ts",
        "dashboard/.env.example",
        ".env.example",
        "plan/README.md",
        "plan/06-produccion-despliegue.md",
        "agents/src/config.py",
        "agents/src/main.py",
      ],
    },
    {
      id: "6.2",
      slug: "diagrama-de-topologia-de-red",
      title: "Diagrama de topología de red",
      status: "generated",
      description:
        "Enseña quién habla con quién cuando el stack Docker está arriba, y los únicos puertos que se abren en la máquina. Postgres, Redis y el resto solo se alcanzan por su nombre dentro de mindos-net.",
      mermaid: `flowchart TB
  cliente["Cliente en la LAN o en Internet"]
  traefik["Traefik<br/>80 redirige a 443"]
  ollama["Ollama del host<br/>host.docker.internal:11434"]
  claude["api.anthropic.com"]
  waCloud["WhatsApp"]
  acme["Let's Encrypt<br/>solo con MINDOS_ACME_EMAIL y DNS público"]

  subgraph red["red bridge mindos-net, sin puertos en el host"]
    gateway["gateway:8000"]
    memory["memory:8001"]
    agents["agents:8002"]
    comms["comms:8003"]
    whatsapp["whatsapp:8004"]
    mcp["mcp:8005"]
    postgres["postgres:5432"]
    redis["redis:6379"]
  end

  cliente -->|"TLS"| traefik
  traefik -->|"HTTP, TLS ya terminado"| gateway
  traefik -.->|"si no, certificado autofirmado"| acme
  gateway -->|"proxy /api/v1"| memory
  gateway -->|"proxy /api/v1"| agents
  gateway -->|"proxy /api/v1"| comms
  gateway -->|"proxy /api/v1"| mcp
  gateway -->|"límite de peticiones"| redis
  mcp -->|"siempre pasa por el Gateway"| gateway
  memory --> postgres
  memory -->|"bus de eventos"| redis
  memory -->|"embeddings"| ollama
  memory -->|"si la captura es una pregunta"| agents
  agents -->|"consulta"| memory
  agents -->|"avisos"| comms
  agents -->|"sin clave de Claude"| ollama
  agents -->|"con clave"| claude
  comms -->|"bus de eventos"| redis
  comms -->|"entrega"| whatsapp
  whatsapp -->|"mensajes entrantes"| comms
  whatsapp -->|"Baileys, solo sale"| waCloud`,
      basedOn: [
        "infra/docker-compose.yml",
        "gateway/src/main.py",
        "gateway/src/config.py",
        "memory/src/main.py",
        "agents/src/config.py",
        "agents/src/main.py",
        "comms/src/main.py",
        "mcp_server/mindos_mcp/config.py",
        "mcp_server/mindos_mcp/main.py",
        ".env.example",
      ],
    },
    {
      id: "6.3",
      slug: "diagrama-de-arquitectura-cloud",
      title: "Diagrama de arquitectura cloud",
      status: "generated",
      description:
        "MindOS se aloja en casa: el conocimiento, la base y los modelos de embeddings no salen del servidor. Fuera viven la API de Claude, WhatsApp, GitHub Actions y el modelo C4 publicado en GitHub Pages.",
      mermaid: `flowchart LR
  persona["Persona"]
  subgraph casa["En casa, sin proveedor de nube"]
    dash["Dashboard<br/>npm en la estación"]
    server["Servidor Ubuntu<br/>Docker Compose, Postgres,<br/>Redis, archivos y Ollama"]
  end
  subgraph fuera["Fuera de casa"]
    claude["API de Claude<br/>api.anthropic.com<br/>modelo claude-sonnet-5-5"]
    wa["WhatsApp"]
    actions["GitHub Actions<br/>revisa, prueba y construye imágenes"]
    pages["GitHub Pages<br/>ddamianzr.github.io/MindOS"]
    acme["Let's Encrypt<br/>opcional, si hay dominio público"]
  end

  persona --> dash
  dash --> server
  persona -.->|"consulta el modelo C4"| pages
  server -->|"asistente, si hay clave"| claude
  server -->|"Baileys, solo saliente"| wa
  server -.->|"si no, certificado autofirmado"| acme`,
      basedOn: [
        "infra/docker-compose.yml",
        "agents/src/main.py",
        "agents/src/config.py",
        ".env.example",
        ".github/workflows/ci.yml",
        ".github/workflows/c4-pages.yml",
        "docs/c4/README.md",
        "whatsapp/src/app.js",
        "plan/README.md",
      ],
    },
    {
      id: "6.4",
      slug: "diagrama-de-pipeline-ci-cd",
      title: "Diagrama de pipeline CI/CD",
      status: "generated",
      description:
        "Sigue lo que GitHub ejecuta al subir cambios: revisar el código, probar y construir las imágenes, y por otro camino publicar el modelo C4. Las imágenes se quedan en el runner: no hay registro ni un paso que las instale en el servidor.",
      mermaid: `flowchart TB
  trigger["push a main o master<br/>o un pull request"]
  lint["job lint-test<br/>Python 3.12"]
  ruff["ruff check ."]
  pytest["pytest, sin pruebas de integración"]
  wa["job whatsapp-test<br/>Node 20"]
  npmtest["npm test en whatsapp/"]
  build["job build-images<br/>espera a los dos jobs"]
  images["docker build, etiqueta :ci<br/>memory, agents, gateway,<br/>comms, whatsapp y mcp<br/>no se publican en un registro"]
  compose["docker compose config<br/>en infra/"]

  c4["cambio en docs/c4<br/>o disparo manual"]
  likec4["npx likec4 build docs/c4"]
  pages["despliegue a GitHub Pages"]

  trigger --> lint
  trigger --> wa
  lint --> ruff --> pytest --> build
  wa --> npmtest --> build
  build --> images --> compose
  c4 --> likec4 --> pages`,
      basedOn: [".github/workflows/ci.yml", ".github/workflows/c4-pages.yml", "docs/c4/README.md"],
    },
    {
      id: "6.5",
      slug: "diagrama-de-ambientes-de-desarrollo",
      title: "Diagrama de ambientes de desarrollo",
      status: "generated",
      description:
        "Compara el arranque local sin Docker, que solo levanta memory, agents y gateway con datos en memoria, el stack de contenedores y el servidor Ubuntu al que ese archivo está destinado. El corte a producción sigue abierto: no hay un script que lleve el compose a esa máquina.",
      mermaid: `flowchart TB
  subgraph local["Sin Docker, scripts/dev_stack.py"]
    memL["memory, 127.0.0.1:8001<br/>base y archivos en memoria<br/>embeddings simulados"]
    agL["agents, 127.0.0.1:8002<br/>Claude si hay clave, si no demostración"]
    gwL["gateway, 127.0.0.1:8000<br/>límite de peticiones en memoria"]
    dashL["Dashboard aparte<br/>npm run dev, puerto 3000"]
  end
  subgraph dockerEnv["Stack Docker, infra/docker-compose.yml"]
    full["postgres, redis y migrate<br/>memory, agents, comms, whatsapp, mcp<br/>gateway y Traefik en 80 y 443<br/>Ollama en el host"]
  end
  subgraph prod["Servidor de producción"]
    ubuntu["Ubuntu 24/7, 16 GB, sin GPU<br/>mismo compose, MINDOS_ENV production<br/>corte del plan todavía abierto"]
  end

  dashL --> gwL
  gwL --> memL
  gwL --> agL
  agL --> memL
  full -.->|"mismo archivo, otro host"| ubuntu`,
      basedOn: [
        "scripts/dev_stack.py",
        "infra/docker-compose.yml",
        "dashboard/src/lib/api-client.ts",
        "plan/README.md",
        "plan/06-produccion-despliegue.md",
        "plan/07-runway-a-produccion.md",
      ],
    },
    {
      id: "6.6",
      slug: "diagrama-de-contenedores-y-orquestacion",
      title: "Diagrama de contenedores y orquestación",
      status: "generated",
      description:
        "Lista cada contenedor, su tope de memoria y a quién espera para arrancar: Docker Compose en un solo host, un proceso por servicio, y las flechas son esa espera, no el tráfico. agents espera a Redis porque el compose lo declara, aunque su código todavía no abre esa conexión.",
      mermaid: `flowchart TB
  migrate["migrate<br/>imagen de memory<br/>alembic upgrade head, no se reinicia"]
  memory["memory, 768m<br/>uvicorn, puerto 8001"]
  agents["agents, 768m<br/>uvicorn, puerto 8002"]
  comms["comms, 256m<br/>uvicorn, puerto 8003"]
  whatsapp["whatsapp, 384m<br/>node, puerto 8004"]
  mcp["mcp, 256m<br/>arranca solo, puerto 8005"]
  gateway["gateway, 256m<br/>uvicorn, puerto 8000"]
  pg["postgres, 2g<br/>pgvector/pgvector:pg16"]
  redis["redis, 512m<br/>redis:7-alpine, AOF"]
  traefik["traefik v3.1, 128m<br/>puertos 80 y 443<br/>lee docker.sock en solo lectura"]
  volPg["volumen postgres_data"]
  volRedis["volumen redis_data"]
  volStorage["volumen storage_data"]
  volWa["volumen whatsapp_auth"]
  volCerts["volumen traefik_certs"]

  migrate -->|"espera"| pg
  memory -->|"espera"| migrate
  memory -->|"espera"| pg
  memory -->|"espera"| redis
  agents -->|"espera"| memory
  agents -->|"espera"| redis
  comms -->|"espera"| redis
  whatsapp -->|"espera"| comms
  gateway -->|"espera"| memory
  gateway -->|"espera"| agents
  gateway -->|"espera"| comms
  gateway -->|"espera"| mcp
  gateway -->|"espera"| redis
  traefik -->|"espera"| gateway
  pg --- volPg
  redis --- volRedis
  memory --- volStorage
  whatsapp --- volWa
  traefik --- volCerts`,
      basedOn: [
        "infra/docker-compose.yml",
        "memory/Dockerfile",
        "agents/Dockerfile",
        "gateway/Dockerfile",
        "comms/Dockerfile",
        "whatsapp/Dockerfile",
        "mcp_server/Dockerfile",
      ],
    },
    {
      id: "6.7",
      slug: "diagrama-de-recuperacion-ante-desastres",
      title: "Diagrama de recuperación ante desastres",
      status: "generated",
      description:
        "Muestra qué queda en el disco del propio servidor si se recrea un contenedor, y qué se pierde con el proceso del asistente. No hay copias fuera de la máquina ni un procedimiento de restauración: el plan los pide y todavía no están en el repositorio.",
      mermaid: `flowchart TB
  evento["Se recrea un contenedor o se reinicia el proceso"]
  politica["restart unless-stopped<br/>migrate no se reinicia"]
  subgraph vive["Sigue en volúmenes locales del host"]
    pg["postgres_data<br/>conocimiento, versiones y grafo"]
    rd["redis_data<br/>appendonly yes"]
    blobs["storage_data<br/>archivos de local_fs"]
    sesion["whatsapp_auth<br/>sesión de Baileys"]
    tls["traefik_certs"]
  end
  subgraph seVa["Se pierde con el proceso de agents"]
    chat["InMemoryConversationStore<br/>conversaciones, tope 200"]
    aprob["InMemoryApprovalStore<br/>aprobaciones pendientes"]
  end

  evento --> politica
  evento -->|"el disco del host sigue"| vive
  evento -->|"la RAM del proceso no"| seVa`,
      basedOn: [
        "infra/docker-compose.yml",
        "agents/src/main.py",
        "agents/src/infrastructure/adapters/in_memory_conversation_store.py",
        "agents/src/infrastructure/adapters/in_memory_approval_store.py",
        "memory/src/infrastructure/adapters/local_fs_storage.py",
        "memory/src/main.py",
        "plan/06-produccion-despliegue.md",
      ],
    },
    {
      id: "6.8",
      slug: "diagrama-de-observabilidad-y-monitoreo",
      title: "Diagrama de observabilidad y monitoreo",
      status: "generated",
      description:
        "Sigue el identificador de cada petición hasta el registro de texto, y las comprobaciones de vida que Docker ya usa. No hay paneles de métricas, trazas ni alertas: /health del Gateway responde 200 aunque el cuerpo diga que un servicio está degradado, así que el contenedor puede seguir contando como sano.",
      mermaid: `flowchart LR
  peticion["Cualquier petición al Gateway"]
  medio["Middleware<br/>crea o reenvía X-Correlation-Id"]
  abajo["Lo reenvía al servicio interno"]
  logs["structlog, a stdout<br/>JSON si MINDOS_ENV es production<br/>consola en desarrollo"]

  subgraph vida["Comprobaciones que existen"]
    gwH["GET /health del Gateway<br/>pregunta a memory, agents, comms y mcp"]
    liv["Esos /health solo dicen<br/>que el proceso responde"]
    datos["postgres: pg_isready<br/>redis: redis-cli ping"]
    waH["whatsapp /health<br/>cuerpo ok o degraded, HTTP 200"]
    imgH["HEALTHCHECK de la imagen, cada 10 s<br/>vale con que el HTTP sea 200"]
    compH["Healthcheck del compose, cada 5 s"]
  end

  peticion --> medio
  medio --> abajo
  medio --> logs
  imgH --> gwH
  imgH --> liv
  gwH --> liv
  imgH --> waH
  compH --> datos`,
      basedOn: [
        "common/mindos_common/logging.py",
        "common/mindos_common/context.py",
        "gateway/src/main.py",
        "memory/src/main.py",
        "agents/src/main.py",
        "comms/src/main.py",
        "mcp_server/mindos_mcp/server.py",
        "whatsapp/src/app.js",
        "infra/docker-compose.yml",
        "gateway/Dockerfile",
        "memory/Dockerfile",
      ],
    },
    {
      id: "6.9",
      slug: "diagrama-de-escalabilidad",
      title: "Diagrama de escalabilidad",
      status: "generated",
      description:
        "Explica el techo de hoy: un proceso por servicio, topes de memoria en el compose y el chat del asistente guardado solo en esa RAM. Duplicar el proceso choca con el disco local y con una sola base. El margen inmediato es la memoria del servidor de 16 GB.",
      mermaid: `flowchart TB
  host["Un solo host de 16 GB<br/>un proyecto Compose, sin réplicas"]
  proc["Un proceso por servicio<br/>uvicorn y node, sin workers"]
  topes["mem_limit del compose<br/>postgres 2g, redis 512m<br/>memory y agents 768m<br/>comms, gateway y mcp 256m<br/>whatsapp 384m, traefik 128m"]
  subgraph traba["Impide una segunda copia del mismo servicio"]
    ram["Chat y aprobaciones<br/>en la RAM de agents"]
    disco["STORAGE_TYPE local_fs<br/>volumen storage_data de ese host"]
    uno["Una sola base Postgres<br/>sin réplica de lectura"]
  end
  subgraph margen["Margen que el codigo ya deja"]
    vertical["Subir un tope<br/>mientras quepa junto a Ollama"]
    ollama["Ollama en el host<br/>qwen3:8b, fuera del compose"]
    limite["Límite de peticiones del Gateway<br/>en Redis, no en la RAM del proceso"]
  end

  host --> proc --> topes --> traba
  host --> margen`,
      basedOn: [
        "infra/docker-compose.yml",
        "agents/Dockerfile",
        "gateway/Dockerfile",
        "memory/Dockerfile",
        "comms/Dockerfile",
        "whatsapp/Dockerfile",
        "mcp_server/Dockerfile",
        "mcp_server/mindos_mcp/main.py",
        "agents/src/main.py",
        "agents/src/infrastructure/adapters/in_memory_conversation_store.py",
        "agents/src/infrastructure/adapters/in_memory_approval_store.py",
        "memory/src/infrastructure/adapters/local_fs_storage.py",
        "memory/src/main.py",
        "gateway/src/main.py",
        "plan/README.md",
      ],
    },
  ],
};
