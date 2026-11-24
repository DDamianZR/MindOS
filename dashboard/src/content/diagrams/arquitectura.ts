import type { DiagramCategory } from "./types";

export const arquitectura: DiagramCategory = {
  id: "3",
  slug: "arquitectura",
  title: "Arquitectura de software",
  summary:
    "Sirve para ver cómo está partido MindOS, qué servicio habla con cuál y qué sistemas de fuera intervienen.",
  diagrams: [
    {
      id: "3.1",
      slug: "modelo-c4-contexto",
      title: "Modelo C4 - Contexto",
      status: "generated",
      description:
        "MindOS como una sola pieza, con la persona que lo usa y los sistemas de fuera con los que habla hoy: WhatsApp, la API de Claude, Ollama y otros asistentes. El modelo interactivo de los niveles 1 y 2 está en https://ddamianzr.github.io/MindOS/.",
      basedOn: [
        "docs/c4/mindos.c4",
        "docs/c4/views.c4",
        "plan/README.md",
        "plan/08-asistente-personal-claude.md",
        "agents/src/main.py",
        "whatsapp/src/index.js",
      ],
      mermaid: `C4Context
title "Contexto de MindOS"
Person(dueno, "Dueño", "Persona única. Captura conocimiento, pregunta y explora su memoria.")
System(mindos, "MindOS", "Guarda, versiona y consulta el conocimiento personal. Nunca borra lo guardado.")
System_Ext(whatsapp, "WhatsApp", "Canal de notas, fotos, audios y documentos.")
System_Ext(claude, "API de Claude", "Anthropic. Responde al asistente y razona en el grafo de agentes.")
System_Ext(ollama, "Ollama", "Embeddings locales. También el modelo si no hay clave de Claude.")
System_Ext(asistentes, "Asistentes externos", "Clientes MCP que usan MindOS como memoria de largo plazo.")
Rel(dueno, mindos, "Captura, pregunta y explora", "Dashboard y REST")
Rel(dueno, whatsapp, "Envía notas y archivos")
Rel(whatsapp, mindos, "Entrega mensajes para guardarlos")
Rel(asistentes, mindos, "Busca y captura", "MCP")
Rel(mindos, claude, "Pide respuestas y planes", "HTTPS")
Rel(mindos, ollama, "Pide embeddings y, si hace falta, un modelo local", "HTTP")`,
    },
    {
      id: "3.2",
      slug: "modelo-c4-contenedores",
      title: "Modelo C4 - Contenedores",
      status: "generated",
      description:
        "MindOS abierto en sus servicios, sus datos y las llamadas que el código hace de verdad. El mismo corte, en modo interactivo, está en https://ddamianzr.github.io/MindOS/.",
      basedOn: [
        "docs/c4/mindos.c4",
        "infra/docker-compose.yml",
        "gateway/src/config.py",
        "gateway/src/main.py",
        "whatsapp/src/comms_client.js",
        "agents/src/config.py",
        "memory/src/config.py",
        "comms/src/config.py",
      ],
      mermaid: `C4Container
title "Contenedores de MindOS"
Person(dueno, "Dueño", "Usa el Dashboard y, por fuera, WhatsApp.")
System_Ext(whatsapp, "WhatsApp", "Mensajería del dueño.")
System_Ext(claude, "API de Claude", "Anthropic. Modelo claude-sonnet-5-5.")
System_Ext(ollama, "Ollama", "En el host. Puerto 11434.")
System_Ext(asistentes, "Asistentes externos", "Clientes MCP, como Claude Desktop.")
Container_Boundary(sistema, "MindOS") {
  Container(traefik, "Traefik", "v3.1", "Única puerta publicada. Puertos 80 y 443.")
  Container(gateway, "Gateway", "FastAPI, 8000", "Autenticación y proxy hacia los servicios.")
  Container(dashboard, "Dashboard", "Next.js, 3000", "Tablero. En desarrollo corre aparte del compose.")
  Container(memory, "Memory", "FastAPI, 8001", "Conocimiento versionado, grafo y búsqueda.")
  Container(agents, "Agents", "FastAPI, 8002", "Asistente y ciclo de plan, ejecución y revisión.")
  Container(comms, "Comms", "FastAPI, 8003", "Entrada y salida de mensajes.")
  Container(puente, "Puente WhatsApp", "Node y Baileys, 8004", "Normaliza lo que llega de WhatsApp.")
  Container(mcp, "Servidor MCP", "Python, 8005", "Herramientas para asistentes externos.")
  ContainerQueue(redis, "Redis", "7, puerto 6379", "Bus de eventos y límite de peticiones del Gateway.")
  ContainerDb(postgres, "PostgreSQL", "16 y pgvector, 5432", "Nodos, versiones, relaciones y vectores.")
  ContainerDb(blobs, "Adjuntos", "Disco local", "Archivos originales. MinIO queda disponible en código.")
}
Rel(dueno, dashboard, "Usa el tablero")
Rel(dueno, traefik, "Entra por HTTPS")
Rel(dashboard, gateway, "Llama a la API", "JSON y SSE")
Rel(traefik, gateway, "Enruta al puerto 8000", "TLS")
Rel(asistentes, mcp, "Invoca herramientas", "MCP")
Rel(mcp, gateway, "Pasa siempre por la API", "API key")
Rel(whatsapp, puente, "Entrega mensajes", "Baileys")
Rel(puente, comms, "Entrega la captura", "POST /api/v1/comms/inbound")
Rel(gateway, memory, "Reenvía memoria, thinking y cognitive")
Rel(gateway, agents, "Reenvía agents y approvals")
Rel(gateway, comms, "Reenvía comms")
Rel(gateway, mcp, "Reenvía mcp")
Rel(gateway, redis, "Cuenta peticiones")
Rel(comms, redis, "Publica mensajes", "mindos.comms")
Rel(memory, redis, "Publica conocimiento y consume capturas")
Rel(memory, postgres, "Lee y escribe", "SQL")
Rel(memory, blobs, "Guarda archivos")
Rel(memory, ollama, "Pide embeddings y clasifica", "HTTP")
Rel(memory, agents, "Si el mensaje es una pregunta", "POST /api/v1/agents/execute")
Rel(agents, memory, "Lee contexto y escribe trazas", "HTTP")
Rel(agents, claude, "Pide el razonamiento del asistente", "HTTPS")
Rel(agents, ollama, "Modelo local si no hay clave", "HTTP")
Rel(agents, comms, "Pide avisar al canal", "POST /api/v1/comms/outbound")
Rel(comms, puente, "Pide enviar la respuesta", "POST /send")`,
    },
    {
      id: "3.3",
      slug: "modelo-c4-componentes",
      title: "Modelo C4 - Componentes",
      status: "existing",
      description:
        "El interior del servicio de memoria: sus rutas, el pipeline de captura, la búsqueda y los almacenes. Es el único nivel de componentes C4 que ya está dibujado.",
      basedOn: ["docs/uml/src/estructura/c4-componentes-memory.puml"],
      svgs: [
        {
          src: "/diagrams/uml/estructura/c4-componentes-memory.svg",
          caption: "Componentes del servicio de memoria.",
        },
      ],
    },
    {
      id: "3.4",
      slug: "modelo-c4-codigo",
      title: "Modelo C4 - Código",
      status: "existing",
      description:
        "Las clases tal como están hoy en cada servicio, en los paquetes compartidos y en el Dashboard. Salen del propio código, no de un dibujo a mano.",
      basedOn: [
        "docs/uml/generated/python/classes_agents.puml",
        "docs/uml/generated/python/classes_common.puml",
        "docs/uml/generated/python/classes_comms.puml",
        "docs/uml/generated/python/classes_gateway.puml",
        "docs/uml/generated/python/classes_mcp_server.puml",
        "docs/uml/generated/python/classes_memory.puml",
        "docs/uml/generated/python/classes_schemas.puml",
        "docs/uml/generated/typescript/dashboard.puml",
      ],
      svgs: [
        {
          src: "/diagrams/uml/generated/python/classes_memory.svg",
          caption: "Clases de Memory.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_agents.svg",
          caption: "Clases de Agents.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_gateway.svg",
          caption: "Clases de Gateway.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_comms.svg",
          caption: "Clases de Comms.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_mcp_server.svg",
          caption: "Clases del servidor MCP.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_schemas.svg",
          caption: "Clases de los contratos compartidos.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_common.svg",
          caption: "Clases de las utilidades compartidas.",
        },
        {
          src: "/diagrams/uml/generated/typescript/dashboard.svg",
          caption: "Clases del Dashboard.",
        },
      ],
    },
    {
      id: "3.5",
      slug: "arquitectura-alto-nivel",
      title: "Diagrama de arquitectura de alto nivel (HLD)",
      status: "generated",
      description:
        "El mapa de conjunto: por dónde entra una persona, qué servicio atiende cada parte y dónde queda el conocimiento. Los servicios internos se llaman entre sí. El Gateway es la puerta para el Dashboard y para los asistentes externos.",
      basedOn: [
        "plan/README.md",
        "plan/08-asistente-personal-claude.md",
        "infra/docker-compose.yml",
        "gateway/src/main.py",
        "gateway/src/config.py",
        "whatsapp/src/comms_client.js",
      ],
      mermaid: `flowchart TB
  dueno["Dueño"]
  dash["Dashboard"]
  traefik["Traefik"]
  gateway["Gateway"]
  mcp["Servidor MCP"]
  asistentes["Asistentes externos"]
  memory["Memory"]
  agents["Agents"]
  comms["Comms"]
  puente["Puente WhatsApp"]
  whatsapp["WhatsApp"]
  redis["Redis Streams"]
  postgres["PostgreSQL y pgvector"]
  blobs["Adjuntos en disco"]
  claude["API de Claude"]
  ollama["Ollama"]
  dueno --> dash
  dueno --> whatsapp
  dash --> gateway
  traefik --> gateway
  asistentes --> mcp
  mcp --> gateway
  gateway --> memory
  gateway --> agents
  gateway --> comms
  gateway --> mcp
  whatsapp --> puente
  puente --> comms
  comms --> redis
  redis --> memory
  memory --> postgres
  memory --> blobs
  memory --> ollama
  memory --> agents
  agents --> memory
  agents --> claude
  agents --> ollama
  agents --> comms
  comms --> puente`,
    },
    {
      id: "3.6",
      slug: "arquitectura-bajo-nivel",
      title: "Diagrama de arquitectura de bajo nivel (LLD)",
      status: "generated",
      description:
        "Cómo Memory guarda un conocimiento: embedding, búsqueda de duplicado, versión en Postgres y aviso en el bus. La contradicción solo se evalúa si el objeto es fact o hypothesis. En desarrollo, esos mismos puertos usan adaptadores en memoria.",
      basedOn: [
        "memory/src/main.py",
        "memory/src/application/services/contradiction_detector.py",
        "memory/src/application/services/ingestion_pipeline.py",
        "memory/src/infrastructure/database/repositories.py",
        "memory/src/infrastructure/vector/pgvector.py",
        "memory/src/infrastructure/adapters/ollama_embedding.py",
        "memory/src/infrastructure/adapters/ollama_llm.py",
      ],
      mermaid: `flowchart TB
  pipeline["IngestionPipelineService"]
  otros["Gateway u otro cliente"]
  ingest["ingest_knowledge"]
  embed["EmbeddingPort.embed_query"]
  ollamaEmb["OllamaEmbedding"]
  dedup["VectorStorePort.search"]
  pgv["PgVectorStoreRepository"]
  save["DatabasePort guarda nodo, versión y fuente"]
  pgr["PgDatabaseRepository"]
  pg["PostgreSQL 16 y pgvector"]
  bus["event_log y stream mindos.memory"]
  tipo{"¿fact o hypothesis?"}
  detector["ContradictionDetectorService"]
  llm["OllamaLlm"]
  pipeline -->|"HTTP interno"| ingest
  otros --> ingest
  ingest --> embed
  embed --> ollamaEmb
  ingest --> dedup
  dedup --> pgv
  ingest --> save
  save --> pgr
  pgr --> pg
  pgv --> pg
  ingest --> bus
  ingest --> tipo
  tipo -->|sí| detector
  tipo -->|no| bus
  detector --> llm`,
    },
    {
      id: "3.7",
      slug: "microservicios",
      title: "Diagrama de microservicios",
      status: "generated",
      description:
        "Los procesos del compose de producción, en la red interna mindos-net, con el puerto en el que escucha cada uno. Solo Traefik publica puertos hacia fuera. El Dashboard no va en este compose.",
      basedOn: [
        "infra/docker-compose.yml",
        "gateway/Dockerfile",
        "memory/Dockerfile",
        "agents/Dockerfile",
        "comms/Dockerfile",
        "mcp_server/Dockerfile",
        "whatsapp/Dockerfile",
      ],
      mermaid: `flowchart TB
  subgraph red ["Red mindos-net"]
    traefik["traefik<br/>80 y 443 publicados"]
    gateway["gateway<br/>8000"]
    memory["memory<br/>8001"]
    agents["agents<br/>8002"]
    comms["comms<br/>8003"]
    whatsapp["whatsapp<br/>8004"]
    mcp["mcp<br/>8005"]
    postgres["postgres<br/>5432"]
    redis["redis<br/>6379"]
    migrate["migrate<br/>un solo uso, sin puerto"]
  end
  traefik --> gateway
  gateway --> memory
  gateway --> agents
  gateway --> comms
  gateway --> mcp
  gateway --> redis
  migrate --> postgres
  memory --> postgres
  memory --> redis
  memory --> agents
  agents --> memory
  agents --> redis
  agents --> comms
  comms --> redis
  comms --> whatsapp
  whatsapp --> comms`,
    },
    {
      id: "3.8",
      slug: "arquitectura-por-capas",
      title: "Diagrama de arquitectura por capas",
      status: "generated",
      description:
        "Las carpetas del servicio de agentes: la API usa la aplicación, la aplicación usa el dominio, y los adaptadores implementan los puertos. El grafo de razonamiento recibe el puerto de la traza. El adaptador que no registra nada es solo el valor por defecto.",
      basedOn: [
        "agents/src/main.py",
        "agents/src/api/assistant_router.py",
        "agents/src/api/approvals_router.py",
        "agents/src/domain/planner/agent_graph.py",
        "agents/src/application/ports/llm.py",
        "agents/src/application/assistant/toolbox.py",
        "agents/src/application/registry/capability_registry_port.py",
        "agents/src/infrastructure/adapters/anthropic_llm.py",
      ],
      mermaid: `flowchart TB
  subgraph capaApi ["api"]
    mainPy["main.py"]
    chatR["assistant_router.py"]
    apprR["approvals_router.py"]
  end
  subgraph capaApp ["application"]
    ports["ports"]
    tools["assistant/toolbox.py"]
    registry["registry/capability_registry_port.py"]
  end
  subgraph capaDom ["domain"]
    planner["planner"]
    executor["executor"]
    reviewer["reviewer"]
    grafo["agent_graph.py"]
  end
  subgraph capaInf ["infrastructure"]
    adapters["adapters"]
  end
  mainPy --> ports
  mainPy --> grafo
  chatR --> ports
  chatR --> tools
  apprR --> ports
  tools --> ports
  grafo --> planner
  grafo --> executor
  grafo --> reviewer
  grafo --> ports
  executor --> registry
  adapters --> ports`,
    },
    {
      id: "3.9",
      slug: "arquitectura-hexagonal",
      title: "Diagrama de arquitectura hexagonal",
      status: "generated",
      description:
        "Los puertos del servicio de agentes y el adaptador que hay detrás de cada uno. Por ahí salen las llamadas a Claude, a Memory y al estado de la conversación. El registro de capacidades está al lado, en application/registry.",
      basedOn: [
        "agents/src/application/ports/llm.py",
        "agents/src/application/ports/personal_agent.py",
        "agents/src/application/ports/conversation_store.py",
        "agents/src/application/ports/memory_gateway.py",
        "agents/src/application/ports/reasoning_recorder.py",
        "agents/src/application/ports/approval.py",
        "agents/src/application/registry/capability_registry_port.py",
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/infrastructure/adapters/http_memory_gateway.py",
        "agents/src/main.py",
      ],
      mermaid: `flowchart TB
  subgraph api ["API y dominio"]
    mainPy["main.py"]
    chat["assistant_router"]
    approvals["approvals_router"]
    grafo["PlannerExecutorReviewerGraph"]
  end
  subgraph puertos ["Puertos"]
    llm["LlmPort"]
    personal["PersonalAgentPort"]
    conversacion["ConversationStorePort"]
    memoria["MemoryGatewayPort"]
    traza["ReasoningRecorderPort"]
    aprobacion["ApprovalPort"]
    registro["CapabilityRegistryPort"]
  end
  subgraph adaptadores ["Adaptadores"]
    anthropic["AnthropicLlm"]
    ollamaLlm["OllamaLlm"]
    mockLlm["MockLlm"]
    claudeAgent["ClaudePersonalAgent"]
    demo["DemoPersonalAgent"]
    convStore["InMemoryConversationStore"]
    httpMem["HttpMemoryGateway"]
    httpRec["HttpReasoningRecorder"]
    noopRec["NoOpReasoningRecorder"]
    approvalStore["InMemoryApprovalStore"]
    capReg["InMemoryCapabilityRegistry"]
  end
  subgraph fuera ["Fuera del servicio"]
    claude["API de Claude"]
    memory["Memory"]
  end
  mainPy --> llm
  mainPy --> grafo
  chat --> personal
  chat --> conversacion
  approvals --> aprobacion
  approvals --> traza
  grafo --> traza
  grafo --> registro
  anthropic --> llm
  ollamaLlm --> llm
  mockLlm --> llm
  claudeAgent --> personal
  demo --> personal
  claudeAgent --> memoria
  convStore --> conversacion
  httpMem --> memoria
  httpRec --> traza
  noopRec --> traza
  approvalStore --> aprobacion
  capReg --> registro
  anthropic --> claude
  claudeAgent --> claude
  httpMem --> memory
  httpRec --> memory`,
    },
    {
      id: "3.10",
      slug: "arquitectura-orientada-a-eventos",
      title: "Diagrama de arquitectura orientada a eventos",
      status: "generated",
      description:
        "Quién publica en Redis Streams y quién está suscrito. El pipeline de memoria es el único consumidor, y solo del stream de mensajes entrantes. Los otros dos streams se publican y, hoy, nadie los lee. El registro durable del conocimiento sigue siendo el event_log de Postgres.",
      basedOn: [
        "common/mindos_common/event_bus.py",
        "schemas/mindos_schemas/events/v1/memory_events.py",
        "schemas/mindos_schemas/events/v1/communication_events.py",
        "comms/src/config.py",
        "comms/src/main.py",
        "comms/src/infrastructure/adapters/event_bus_inbound_handler.py",
        "memory/src/main.py",
      ],
      mermaid: `flowchart LR
  commsIn["Comms publica<br/>message.received"]
  commsOut["Comms publica<br/>message.sent"]
  memoryPub["Memory publica<br/>knowledge, relation y contradiction"]
  streamIn["mindos.comms"]
  streamOut["mindos.comms.outbound"]
  streamMem["mindos.memory"]
  pipeline["Memory<br/>grupo memory-ingestion-pipeline"]
  nadieOut["Sin consumidor"]
  nadieMem["Sin consumidor"]
  commsIn --> streamIn
  streamIn --> pipeline
  commsOut --> streamOut
  streamOut --> nadieOut
  memoryPub --> streamMem
  streamMem --> nadieMem`,
    },
    {
      id: "3.11",
      slug: "integracion-de-sistemas",
      title: "Diagrama de integración de sistemas",
      status: "generated",
      description:
        "Los sistemas de fuera que el código llama de verdad. Claude atiende al asistente. Ollama calcula embeddings y, si no hay clave, el razonamiento local. El texto de fotos y audios se saca dentro de Memory. Los archivos van al disco. MinIO está en el código por si el almacén pasa a ser remoto.",
      basedOn: [
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/infrastructure/adapters/anthropic_llm.py",
        "agents/src/infrastructure/adapters/ollama_llm.py",
        "agents/src/main.py",
        "memory/src/config.py",
        "memory/src/infrastructure/adapters/ollama_embedding.py",
        "memory/src/infrastructure/adapters/tesseract_ocr.py",
        "memory/src/infrastructure/adapters/faster_whisper_stt.py",
        "memory/src/infrastructure/adapters/minio_storage.py",
        "memory/src/infrastructure/adapters/local_fs_storage.py",
        "whatsapp/src/index.js",
        "comms/src/infrastructure/adapters/whatsapp_outbound_adapter.py",
      ],
      mermaid: `flowchart LR
  subgraph mindos ["MindOS"]
    agents["Agents"]
    memory["Memory"]
    comms["Comms"]
    puente["Puente WhatsApp"]
  end
  claude["API de Claude<br/>claude-sonnet-5-5"]
  ollama["Ollama<br/>nomic-embed-text"]
  tesseract["Tesseract"]
  whisper["faster-whisper"]
  disco["Disco local"]
  minio["MinIO"]
  whatsapp["WhatsApp"]
  agents -->|"asistente y grafo, si hay clave"| claude
  agents -->|"LLM_PROVIDER ollama"| ollama
  memory -->|"embeddings y clasificación"| ollama
  memory -->|"OCR de imagen y PDF"| tesseract
  memory -->|"transcripción de audio"| whisper
  memory -->|"STORAGE_TYPE local_fs"| disco
  memory -->|"STORAGE_TYPE minio"| minio
  puente -->|"Baileys"| whatsapp
  comms -->|"POST /send"| puente`,
    },
    {
      id: "3.12",
      slug: "dependencias",
      title: "Diagrama de dependencias",
      status: "generated",
      description:
        "Qué parte del monorepo depende de cuál. Los servicios Python importan los contratos y las utilidades. El Gateway solo importa las utilidades: reenvía el JSON sin leer los contratos. El Dashboard, el puente y el servidor MCP no importan esos paquetes. Hablan por HTTP.",
      basedOn: [
        "schemas/pyproject.toml",
        "common/pyproject.toml",
        "memory/requirements.txt",
        "agents/requirements.txt",
        "gateway/requirements.txt",
        "comms/requirements.txt",
        "mcp_server/pyproject.toml",
        "dashboard/package.json",
        "gateway/src/main.py",
        "whatsapp/src/comms_client.js",
        "mcp_server/mindos_mcp/main.py",
      ],
      mermaid: `flowchart TB
  schemas["mindos_schemas"]
  common["mindos_common"]
  memory["memory"]
  agents["agents"]
  comms["comms"]
  gateway["gateway"]
  mcp["mcp_server"]
  dashboard["dashboard"]
  whatsapp["whatsapp"]
  memory -->|importa| schemas
  memory -->|importa| common
  agents -->|importa| schemas
  agents -->|importa| common
  comms -->|importa| schemas
  comms -->|importa| common
  gateway -->|importa| common
  mcp -->|HTTP| gateway
  dashboard -->|HTTP| gateway
  whatsapp -->|HTTP| comms`,
    },
    {
      id: "3.13",
      slug: "comunicacion-entre-apis",
      title: "Diagrama de comunicación entre APIs",
      status: "generated",
      description:
        "Una búsqueda y un turno del asistente, desde el Dashboard hasta el servicio, siempre por el Gateway. El chat vuelve como un flujo de eventos, sin esperar a que termine la respuesta. Las herramientas del asistente llaman a Memory directo, no otra vez por el Gateway.",
      basedOn: [
        "dashboard/src/lib/api-client.ts",
        "dashboard/src/lib/assistant-client.ts",
        "gateway/src/main.py",
        "gateway/src/config.py",
        "agents/src/api/assistant_router.py",
        "agents/src/infrastructure/adapters/http_memory_gateway.py",
      ],
      mermaid: `sequenceDiagram
  participant Dash as Dashboard
  participant Gw as Gateway
  participant Mem as Memory
  participant Ag as Agents
  Dash->>Gw: POST /api/v1/auth/login
  Gw-->>Dash: JWT de sesión
  Dash->>Gw: POST /api/v1/memory/search
  Gw->>Mem: POST /api/v1/memory/search
  Mem-->>Gw: JSON
  Gw-->>Dash: JSON
  Dash->>Gw: POST /api/v1/agents/assistant/chat
  Note over Dash,Gw: Pide text/event-stream
  Gw->>Ag: POST /api/v1/agents/assistant/chat
  Ag-->>Gw: SSE
  Gw-->>Dash: SSE sin buffer
  Note over Ag,Mem: Las herramientas llaman a Memory por MEMORY_URL`,
    },
  ],
};
