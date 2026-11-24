import type { DiagramCategory } from "./types";

export const inteligenciaArtificial: DiagramCategory = {
  id: "8",
  slug: "inteligencia-artificial",
  title: "Inteligencia artificial",
  summary:
    "Cómo el asistente y el grafo de metas consultan la memoria, razonan con un modelo y piden confirmación antes de actuar.",
  diagrams: [
    {
      id: "8.1",
      slug: "arquitectura-de-agentes",
      title: "Diagrama de arquitectura de agentes",
      status: "generated",
      description:
        "Muestra los dos agentes que hay hoy: el asistente con el que conversas y el grafo que cumple una meta. Los dos leen y escriben la misma memoria.",
      mermaid: `flowchart TD
  persona["Persona"] --> gateway["Gateway"]
  gateway --> chat["POST /api/v1/agents/assistant/chat"]
  gateway --> meta["POST /api/v1/agents/execute"]
  chat --> proveedor{"resolve_llm_provider"}
  proveedor -->|anthropic| claude["ClaudePersonalAgent<br/>claude-sonnet-5-5"]
  proveedor -->|ollama o mock| demo["DemoPersonalAgent"]
  claude --> caja["AssistantToolbox"]
  demo --> caja
  caja --> memoria["Memory Service"]
  meta --> contexto["POST /api/v1/memory/context"]
  contexto --> grafo["PlannerExecutorReviewerGraph"]
  grafo --> planner["LlmPlanner"]
  grafo --> executor["CapabilityExecutor"]
  grafo --> reviewer["LlmReviewer"]
  planner --> llm["get_llm_port"]
  reviewer --> llm
  executor --> registro["CapabilityRegistry"]
  registro --> memoria
  grafo --> traza["HttpReasoningRecorder"]
  traza --> thinking["Thinking Graph"]`,
      basedOn: [
        "agents/src/main.py",
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/infrastructure/adapters/demo_personal_agent.py",
        "agents/src/application/assistant/toolbox.py",
        "agents/src/domain/planner/agent_graph.py",
        "agents/src/domain/executor/capability_executor.py",
        "agents/src/infrastructure/adapters/http_reasoning_recorder.py",
        "plan/08-asistente-personal-claude.md",
      ],
    },
    {
      id: "8.2",
      slug: "orquestacion-multiagente",
      title: "Diagrama de orquestación multiagente",
      status: "generated",
      description:
        "Planner, Executor y Reviewer son tres roles del mismo proceso LangGraph, no agentes independientes. Si el revisor rechaza un paso, se replanifica hasta max_retries (3); si hace falta tu aprobación, el grafo se detiene.",
      mermaid: `flowchart TD
  entrada["Meta, contexto GraphRAG y capacidades"] --> plan_step["plan_step<br/>LlmPlanner"]
  plan_step --> execute_step["execute_step<br/>CapabilityExecutor"]
  execute_step --> tras{"_after_execute"}
  tras -->|pending_approval| pausa["Episodio pending_approval"]
  tras -->|review| review_step["review_step<br/>LlmReviewer"]
  review_step --> sigue{"_should_continue"}
  sigue -->|continue| execute_step
  sigue -->|replan| plan_step
  sigue -->|termina| cierre["completed o failed"]
  traza["start_episode y record_step<br/>kind plan execute review replan"] --> plan_step`,
      basedOn: [
        "agents/src/domain/planner/agent_graph.py",
        "agents/src/domain/planner/llm_planner.py",
        "agents/src/domain/planner/llm_reviewer.py",
        "agents/src/domain/executor/capability_executor.py",
        "agents/src/main.py",
      ],
    },
    {
      id: "8.3",
      slug: "pipeline-rag",
      title: "Diagrama de pipeline RAG",
      status: "generated",
      description:
        "Muestra cómo una consulta se vuelve fragmentos citables: primero por parecido de significado, luego por las relaciones del grafo, y al final ordenados por parecido, importancia, recencia y confianza.",
      mermaid: `flowchart TD
  consulta["Consulta"] --> embed["EmbeddingPort.embed_query"]
  embed --> semillas["vector_store.search<br/>semillas top-k"]
  semillas --> expansion["query_relations_recursive<br/>similitud heredada por graph_expansion_decay 0.7"]
  expansion --> activas["get_latest_node_version<br/>sin archivados"]
  activas --> rerank["Puntaje lineal<br/>similitud 0.5<br/>importancia 0.2<br/>recencia 0.15<br/>confianza 0.15"]
  rerank --> corte["Los limit primeros"]
  corte --> fragmentos["ContextFragment<br/>citation_label node_id version source_id"]
  corte --> linea["timeline<br/>hasta 5 hitos"]
  corte --> relaciones["relations_summary"]`,
      basedOn: [
        "memory/src/application/services/context_builder.py",
        "memory/src/config.py",
        "memory/src/main.py",
      ],
    },
    {
      id: "8.4",
      slug: "invocacion-de-herramientas",
      title: "Diagrama de invocación de herramientas",
      status: "generated",
      description:
        "Muestra un turno en el que el asistente puede pedir varias consultas de memoria a la vez: se ejecutan en paralelo y todos los resultados vuelven en un solo mensaje. La búsqueda y la lectura web corren en los servidores de Anthropic.",
      mermaid: `sequenceDiagram
  participant UI as Interfaz
  participant R as assistant_router
  participant A as ClaudePersonalAgent
  participant API as API de Claude
  participant Caja as AssistantToolbox

  UI->>R: POST /api/v1/agents/assistant/chat
  R-->>UI: evento conversation
  A->>API: system tools y messages en streaming
  API-->>A: thinking_delta y text_delta
  A-->>UI: eventos thinking y text
  alt pause_turn
    Note over API: web_search y web_fetch las resuelve Anthropic
    A->>API: reenvia el turno y continua
  else tool_use de memoria
    A-->>UI: tool_start por cada llamada
    A->>Caja: ejecuta todas en paralelo
    Caja-->>A: ToolOutcome de cada una
    A-->>UI: tool_end
    A->>API: un solo mensaje user con todos los tool_result
  else sin herramientas
    A-->>UI: evento done
  else error rechazo tope o JSON ilegible
    A-->>UI: evento error o restart
    Note over A: rollback del historial desde el checkpoint
  end`,
      basedOn: [
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/application/assistant/toolbox.py",
        "agents/src/application/ports/personal_agent.py",
        "agents/src/api/assistant_router.py",
        "agents/src/config.py",
      ],
    },
    {
      id: "8.5",
      slug: "integracion-mcp",
      title: "Diagrama de integración MCP",
      status: "generated",
      description:
        "Muestra el servidor MCP que otros asistentes pueden usar para buscar, guardar y explicar tu memoria. Por HTTP pasa dos puertas: la del Gateway y una clave propia del servidor.",
      mermaid: `flowchart TD
  local["Cliente local"] --> stdio["transporte stdio"]
  remoto["Cliente remoto"] --> puerta["Gateway require_auth<br/>JWT Bearer o X-Api-Key"]
  puerta --> proxy["proxy /api/v1/mcp/mcp"]
  proxy --> propia["ApiKeyAuthMiddleware<br/>MCP_API_KEY"]
  stdio --> tools["mindos_search<br/>mindos_ingest<br/>mindos_context<br/>mindos_ask_cognitive<br/>mindos_explain"]
  propia --> tools
  tools --> cliente["MindOSClient"]
  cliente --> vuelta["Gateway con X-Api-Key"]
  vuelta --> memoria["Memory<br/>search ingest context cognitive explain"]
  salud["GET /health sin clave"] --> propioSrv["Servidor MCP"]`,
      basedOn: [
        "mcp_server/mindos_mcp/server.py",
        "mcp_server/mindos_mcp/tools.py",
        "mcp_server/mindos_mcp/main.py",
        "mcp_server/mindos_mcp/auth_middleware.py",
        "mcp_server/mindos_mcp/mindos_client.py",
        "gateway/src/main.py",
        "gateway/src/config.py",
      ],
    },
    {
      id: "8.6",
      slug: "integracion-acp",
      title: "Diagrama de integración ACP",
      status: "not_applicable",
      description: "No hay un protocolo para que agentes separados se envíen tareas entre sí.",
      reason:
        "En el repositorio no hay Agent Communication Protocol. Aplicaría si Planner, Executor y Reviewer vivieran en procesos distintos y se hablaran por mensajes; hoy comparten un grafo LangGraph dentro de Agents.",
      basedOn: [],
    },
    {
      id: "8.7",
      slug: "estados-de-agentes",
      title: "Diagrama de estados de agentes",
      status: "generated",
      description:
        "Muestra los estados de una respuesta del asistente, con deshacer el turno si falla, y los de una meta del grafo, incluida la espera de tu aprobación.",
      mermaid: `stateDiagram-v2
  state "Turno del asistente" as turno {
    [*] --> enCurso
    enCurso --> ejecutando: tool_use
    ejecutando --> enCurso: resultados listos
    enCurso --> enCurso: pause_turn
    enCurso --> enCurso: restart
    enCurso --> terminado: done
    enCurso --> fallido: error o rechazo
    ejecutando --> fallido: tope de rondas
    fallido --> deshecho: rollback del historial
  }
  state "Episodio del grafo" as episodio {
    [*] --> running
    running --> completed
    running --> failed
    running --> pending_approval
    pending_approval --> completed: aprobada y ejecutada
    pending_approval --> failed: aprobada y el despacho falla
    pending_approval --> rejected: rechazada
  }`,
      basedOn: [
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/application/ports/personal_agent.py",
        "agents/src/api/assistant_router.py",
        "agents/src/main.py",
        "agents/src/api/approvals_router.py",
        "schemas/mindos_schemas/api/v1/thinking_dto.py",
      ],
    },
    {
      id: "8.8",
      slug: "human-in-the-loop",
      title: "Diagrama Human-in-the-loop",
      status: "generated",
      description:
        "Muestra dos pausas que dependen de ti: una capacidad sensible no se ejecuta hasta que la apruebas, y una rutina que propone el asistente nace pendiente hasta que la activas.",
      mermaid: `flowchart TD
  subgraph aprobacion ["Capacidad sensible"]
    cap["requires_approval"] --> freno["execute_step se detiene"]
    freno --> solicitud["ApprovalRequest pending"]
    solicitud --> aviso["Aviso por comms si hay reply_to"]
    solicitud --> resolve["POST /api/v1/approvals/approval_id/resolve"]
    resolve -->|aprobada| despacho["execute_capability_by_name"]
    resolve -->|rechazada| rechazada["episodio rejected"]
    despacho -->|completed| hecha["episodio completed"]
    despacho -->|failed| mal["episodio failed"]
  end
  subgraph rutinas ["Rutina del asistente"]
    propuesta["RoutineDto created_by assistant"] --> pendiente["pending_activation"]
    pendiente -->|la persona la activa| activa["active"]
    activa --> pausada["paused"]
    activa --> archivada["archived"]
    pausada --> archivada
  end`,
      basedOn: [
        "agents/src/domain/executor/capability_executor.py",
        "agents/src/domain/planner/agent_graph.py",
        "agents/src/api/approvals_router.py",
        "agents/src/config.py",
        "schemas/mindos_schemas/api/v1/routine_dto.py",
        "schemas/mindos_schemas/api/v1/approval_dto.py",
      ],
    },
    {
      id: "8.9",
      slug: "arquitectura-de-memoria",
      title: "Diagrama de arquitectura de memoria",
      status: "generated",
      description:
        "Muestra el conocimiento como objetos con versiones, el origen de cada captura, las relaciones con tipo y fecha, el grafo de cómo se razonó y la consulta de lo que estaba vigente en un momento.",
      mermaid: `flowchart TD
  ingesta["POST /api/v1/memory/ingest"] --> nodos["knowledge_nodes<br/>object_type"]
  nodos --> versiones["knowledge_node_versions<br/>version parent_version_id evidence confidence importance"]
  versiones --> fuentes["sources<br/>kind uri raw_ref"]
  versiones --> vector["embedding"]
  nodos --> relaciones["relations<br/>relation_type valid_from valid_to"]
  tipos["RelationType<br/>SUPPORTS CONTRADICTS DUPLICATE_OF PART_OF DERIVED_FROM"] --> relaciones
  asof["GET /api/v1/memory/timetravel"] --> versiones
  asof --> relaciones
  episodios["reasoning_episodes"] --> pasos["reasoning_steps<br/>plan execute review replan"]
  pasos --> citas["knowledge_refs"]
  citas --> nodos`,
      basedOn: [
        "memory/src/infrastructure/database/models.py",
        "memory/src/main.py",
        "schemas/mindos_schemas/domain/relation_type.py",
        "memory/src/infrastructure/database/thinking_graph_repository.py",
        "memory/alembic/versions/0004_thinking_graph.py",
      ],
    },
    {
      id: "8.10",
      slug: "enrutamiento-de-modelos",
      title: "Diagrama de enrutamiento de modelos",
      status: "generated",
      description:
        "Muestra que con credencial de Claude el razonamiento va a claude-sonnet-5-5, y sin ella el grafo usa un modelo local en producción o un doble de prueba. Si Anthropic releva o rechaza el turno, el historial no se queda a medias.",
      mermaid: `flowchart TD
  entrada["resolve_llm_provider"] --> auto{"LLM_PROVIDER es auto"}
  auto -->|no| fijo["se usa el valor tal cual"]
  auto -->|si| cred{"ANTHROPIC_API_KEY o ANTHROPIC_AUTH_TOKEN"}
  cred -->|presente| ant["anthropic"]
  cred -->|ausente y MINDOS_ENV production| oll["ollama"]
  cred -->|ausente en otro entorno| mok["mock"]
  ant --> chat["ClaudePersonalAgent"]
  ant --> llmA["AnthropicLlm<br/>Planner y Reviewer"]
  oll --> demo["DemoPersonalAgent"]
  mok --> demo
  oll --> llmO["OllamaLlm<br/>OLLAMA_MODEL"]
  mok --> llmM["MockLlm"]
  chat --> fb["ANTHROPIC_FALLBACKS"]
  llmA --> fb
  fb --> beta["beta server-side-fallback-2026-07-01<br/>fallbacks default"]
  beta --> filtro["no se reenvian thinking ni tool_use anteriores al bloque fallback"]
  chat --> refusal["stop_reason refusal<br/>rollback del turno"]`,
      basedOn: [
        "agents/src/main.py",
        "agents/src/config.py",
        "agents/src/infrastructure/adapters/anthropic_llm.py",
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/infrastructure/adapters/ollama_llm.py",
        "agents/src/infrastructure/adapters/mock_llm.py",
        "plan/08-asistente-personal-claude.md",
      ],
    },
    {
      id: "8.11",
      slug: "inferencia",
      title: "Diagrama de inferencia",
      status: "generated",
      description:
        "Muestra un turno de respuesta: instrucciones estables que se reutilizan, el contexto de esta conversación, las herramientas y el texto que va llegando a la interfaz.",
      mermaid: `sequenceDiagram
  participant UI as Interfaz
  participant R as assistant_router
  participant A as ClaudePersonalAgent
  participant API as API de Claude

  UI->>R: POST /api/v1/agents/assistant/chat
  R-->>UI: SSE conversation
  Note over A: BASE_SYSTEM_PROMPT con cache ephemeral
  Note over A: conversation_context fijo al abrir el chat
  Note over A: tools de orden estable y cache_control del historial
  A->>API: thinking adaptive display summarized y effort
  API-->>A: thinking_delta
  A-->>UI: evento thinking
  API-->>A: text_delta
  A-->>UI: evento text
  opt hay tool_use y no se supera ASSISTANT_MAX_TOOL_ROUNDS
    A-->>UI: tool_start y tool_end
    A->>API: siguiente peticion con el historial solo-anexar
  end
  A-->>UI: evento done con modelo y usage
  Note over UI: un fallo viaja como evento error`,
      basedOn: [
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/application/assistant/system_prompt.py",
        "agents/src/api/assistant_router.py",
        "agents/src/application/ports/personal_agent.py",
        "agents/src/config.py",
      ],
    },
    {
      id: "8.12",
      slug: "procesamiento-de-embeddings",
      title: "Diagrama de procesamiento de embeddings",
      status: "generated",
      description:
        "Muestra cómo el texto pasa a un vector de 768 números con nomic-embed-text, se guarda para buscar parecidos y sirve para no duplicar notas y para detectar afirmaciones que se contradicen.",
      mermaid: `flowchart TD
  texto["Texto"] --> prov{"EMBEDDING_PROVIDER"}
  prov -->|ollama| ollama["OllamaEmbedding<br/>POST /api/embeddings<br/>nomic-embed-text 768"]
  prov -->|mock| falso["MockEmbedding"]
  ollama --> vector["vector"]
  falso --> vector
  vector --> base{"DATABASE_TYPE"}
  base -->|postgres| hnsw["knowledge_node_versions.embedding<br/>HNSW ix_versions_embedding<br/>vector_cosine_ops"]
  base -->|in_memory| memoria["InMemoryVectorStore"]
  hnsw --> vecino["vecino mas cercano<br/>score es 1 menos distancia coseno"]
  memoria --> vecino
  vecino --> modo{"on_duplicate si score llega a 0.92"}
  modo -->|link| dup["relacion DUPLICATE_OF"]
  modo -->|new_version| misma["nueva version del mismo node_id"]
  modo -->|force_new o por debajo| nuevo["nodo nuevo"]
  vecino --> filtro["solo fact o hypothesis<br/>umbral 0.65"]
  filtro --> juez["OllamaLlm qwen3:8b o MockLlm"]
  juez -->|contradicts| arista["relacion CONTRADICTS"]`,
      basedOn: [
        "memory/src/infrastructure/adapters/ollama_embedding.py",
        "memory/src/infrastructure/adapters/mock_embedding.py",
        "memory/src/infrastructure/vector/pgvector.py",
        "memory/src/infrastructure/adapters/in_memory_vector_store.py",
        "memory/src/infrastructure/database/models.py",
        "memory/src/main.py",
        "memory/src/config.py",
        "memory/src/application/services/contradiction_detector.py",
        "memory/alembic/versions/0001_initial_schema.py",
        "schemas/mindos_schemas/api/v1/memory_dto.py",
      ],
    },
    {
      id: "8.13",
      slug: "evaluacion-de-modelos",
      title: "Diagrama de evaluación de modelos",
      status: "not_applicable",
      description: "No hay una prueba repetible que mida la calidad de las respuestas ni de las citas.",
      reason:
        "El plan de automatización describe casos dorados y un juez, pero no hay harness ni un reporte de evaluación en el código. Aplicaría cuando esa medición exista. MindOS no entrena modelos: solo elige entre Claude, Ollama y un doble de prueba.",
      basedOn: [],
    },
    {
      id: "8.14",
      slug: "pipeline-mlops",
      title: "Diagrama de pipeline MLOps",
      status: "not_applicable",
      description: "No hay un proceso de entrenamiento, registro ni publicación de modelos propios.",
      reason:
        "MindOS no entrena modelos. El asistente llama a la API de Claude y los vectores salen de nomic-embed-text en Ollama, ya entrenado. Un pipeline MLOps aplicaría si hubiera entrenamiento, un registro de artefactos o promoción entre entornos.",
      basedOn: [],
    },
  ],
};
