import type { DiagramCategory } from "./types";

export const uml: DiagramCategory = {
  id: "1",
  slug: "uml",
  title: "UML",
  summary:
    "Muestra para qué usa la persona MindOS, cómo están armados los servicios y cómo se hablan en un turno.",
  diagrams: [
    {
      id: "1.1",
      slug: "casos-de-uso",
      title: "Diagrama de casos de uso",
      status: "existing",
      description:
        "Qué puede hacer la persona con MindOS: capturar por los canales que ya existen, y consultar, explicar o pedir una meta al asistente.",
      svgs: [
        {
          src: "/diagrams/uml/comportamiento/casos-de-uso-captura.svg",
          caption: "Canales de captura y lo que dispara cada uno.",
        },
        {
          src: "/diagrams/uml/comportamiento/casos-de-uso-consulta.svg",
          caption: "Búsqueda, contexto, preguntas, explicación, metas y aprobaciones.",
        },
      ],
      basedOn: [
        "docs/uml/src/comportamiento/casos-de-uso-captura.puml",
        "docs/uml/src/comportamiento/casos-de-uso-consulta.puml",
      ],
    },
    {
      id: "1.2",
      slug: "clases",
      title: "Diagrama de clases",
      status: "existing",
      description:
        "Las clases del conocimiento versionado, de la memoria, de los agentes y las que salen solas al leer el código de cada servicio.",
      svgs: [
        {
          src: "/diagrams/uml/estructura/clases-dominio.svg",
          caption: "Objeto cognitivo, versiones, fuente, relaciones y episodios de razonamiento.",
        },
        {
          src: "/diagrams/uml/estructura/clases-memory-hexagonal.svg",
          caption: "Puertos del servicio de memoria y los adaptadores que los cumplen.",
        },
        {
          src: "/diagrams/uml/estructura/clases-agents.svg",
          caption: "Planner, Executor y Reviewer, con el estado que comparten en LangGraph.",
        },
        {
          src: "/diagrams/modelo-dominio/00-modelo-dominio.svg",
          caption: "Vista de conjunto del modelo de dominio.",
        },
        {
          src: "/diagrams/modelo-dominio/01-conocimiento.svg",
          caption: "Conocimiento: objetos, versiones, fuentes y relaciones.",
        },
        {
          src: "/diagrams/modelo-dominio/02-razonamiento-agentes.svg",
          caption: "Razonamiento del agente y episodios.",
        },
        {
          src: "/diagrams/modelo-dominio/03-comunicacion-eventos.svg",
          caption: "Mensajes y eventos entre canales.",
        },
        {
          src: "/diagrams/modelo-dominio/04-servicios-ia-puertos.svg",
          caption: "Puertos hacia modelo, embeddings, OCR y transcripción.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_memory.svg",
          caption: "Clases de Python del servicio de memoria, leídas del código.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_agents.svg",
          caption: "Clases de Python del servicio de agentes, leídas del código.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_gateway.svg",
          caption: "Clases de Python del Gateway, leídas del código.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_comms.svg",
          caption: "Clases de Python de comunicaciones, leídas del código.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_mcp_server.svg",
          caption: "Clases de Python del servidor MCP, leídas del código.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_common.svg",
          caption: "Clases de Python compartidas, leídas del código.",
        },
        {
          src: "/diagrams/uml/generated/python/classes_schemas.svg",
          caption: "Clases de los contratos compartidos, leídas del código.",
        },
        {
          src: "/diagrams/uml/generated/typescript/dashboard.svg",
          caption: "Tipos de TypeScript del Dashboard, leídos del código.",
        },
      ],
      basedOn: [
        "docs/uml/src/estructura/clases-dominio.puml",
        "docs/uml/src/estructura/clases-memory-hexagonal.puml",
        "docs/uml/src/estructura/clases-agents.puml",
        "docs/modelo-dominio/src/clases/00-modelo-dominio.puml",
        "docs/modelo-dominio/src/clases/01-conocimiento.puml",
        "docs/modelo-dominio/src/clases/02-razonamiento-agentes.puml",
        "docs/modelo-dominio/src/clases/03-comunicacion-eventos.puml",
        "docs/modelo-dominio/src/clases/04-servicios-ia-puertos.puml",
        "docs/uml/generated/python/classes_memory.puml",
        "docs/uml/generated/python/classes_agents.puml",
        "docs/uml/generated/python/classes_gateway.puml",
        "docs/uml/generated/python/classes_comms.puml",
        "docs/uml/generated/python/classes_mcp_server.puml",
        "docs/uml/generated/python/classes_common.puml",
        "docs/uml/generated/python/classes_schemas.puml",
        "docs/uml/generated/typescript/dashboard.puml",
      ],
    },
    {
      id: "1.3",
      slug: "secuencia",
      title: "Diagrama de secuencia",
      status: "existing",
      description:
        "El orden de los mensajes en cuatro recorridos que ya están construidos: entrar por el Gateway, capturar, ejecutar una meta y resolver una aprobación.",
      svgs: [
        {
          src: "/diagrams/uml/interaccion/secuencia-gateway-auth.svg",
          caption: "Login, sesión y reenvío autenticado a un servicio.",
        },
        {
          src: "/diagrams/uml/interaccion/secuencia-captura-whatsapp.svg",
          caption: "Un mensaje de WhatsApp hasta la ingesta y el auto-enlace.",
        },
        {
          src: "/diagrams/uml/interaccion/secuencia-ejecucion-agente.svg",
          caption: "Una meta: contexto, ciclo del agente, traza y resultado guardado.",
        },
        {
          src: "/diagrams/uml/interaccion/secuencia-aprobacion.svg",
          caption: "Una aprobación pendiente que se resuelve desde el Dashboard.",
        },
      ],
      basedOn: [
        "docs/uml/src/interaccion/secuencia-gateway-auth.puml",
        "docs/uml/src/interaccion/secuencia-captura-whatsapp.puml",
        "docs/uml/src/interaccion/secuencia-ejecucion-agente.puml",
        "docs/uml/src/interaccion/secuencia-aprobacion.puml",
      ],
    },
    {
      id: "1.4",
      slug: "actividades",
      title: "Diagrama de actividades",
      status: "existing",
      description:
        "Los pasos de la ingesta, del ciclo del agente y de los recorridos del modelo de dominio, desde la captura hasta la explicación.",
      svgs: [
        {
          src: "/diagrams/uml/comportamiento/actividad-ingesta.svg",
          caption: "Ingesta de un objeto: deduplicación, fuente, eventos y contradicciones.",
        },
        {
          src: "/diagrams/uml/comportamiento/actividad-agente-langgraph.svg",
          caption: "Plan, ejecución y revisión, con reintento, replan y pausa por aprobación.",
        },
        {
          src: "/diagrams/modelo-dominio/A1-captura-multimodal.svg",
          caption: "Captura de texto, imagen, audio o documento.",
        },
        {
          src: "/diagrams/modelo-dominio/A2-ingesta-dedup-versionado.svg",
          caption: "Ingesta con deduplicación y una versión nueva.",
        },
        {
          src: "/diagrams/modelo-dominio/A3-deteccion-contradicciones.svg",
          caption: "Detección de contradicciones entre notas parecidas.",
        },
        {
          src: "/diagrams/modelo-dominio/A4-auto-enlazado.svg",
          caption: "Propuesta de relaciones por parecido.",
        },
        {
          src: "/diagrams/modelo-dominio/A5-graphrag-contexto.svg",
          caption: "Armado del contexto que cita nodos.",
        },
        {
          src: "/diagrams/modelo-dominio/A6-ciclo-planner-executor-reviewer.svg",
          caption: "Ciclo Planner, Executor y Reviewer.",
        },
        {
          src: "/diagrams/modelo-dominio/A7-aprobacion-humana.svg",
          caption: "Pausa hasta que la persona aprueba o rechaza.",
        },
        {
          src: "/diagrams/modelo-dominio/A8-explicabilidad.svg",
          caption: "Recorrido hacia atrás de lo que sostiene un nodo.",
        },
      ],
      basedOn: [
        "docs/uml/src/comportamiento/actividad-ingesta.puml",
        "docs/uml/src/comportamiento/actividad-agente-langgraph.puml",
        "docs/modelo-dominio/src/actividades/A1-captura-multimodal.puml",
        "docs/modelo-dominio/src/actividades/A2-ingesta-dedup-versionado.puml",
        "docs/modelo-dominio/src/actividades/A3-deteccion-contradicciones.puml",
        "docs/modelo-dominio/src/actividades/A4-auto-enlazado.puml",
        "docs/modelo-dominio/src/actividades/A5-graphrag-contexto.puml",
        "docs/modelo-dominio/src/actividades/A6-ciclo-planner-executor-reviewer.puml",
        "docs/modelo-dominio/src/actividades/A7-aprobacion-humana.puml",
        "docs/modelo-dominio/src/actividades/A8-explicabilidad.puml",
      ],
    },
    {
      id: "1.5",
      slug: "estados",
      title: "Diagrama de estados",
      status: "existing",
      description:
        "En qué estados puede estar una versión de un objeto de conocimiento, y en cuáles un episodio de razonamiento o una aprobación.",
      svgs: [
        {
          src: "/diagrams/uml/comportamiento/estados-objeto-cognitivo.svg",
          caption: "Versiones, archivo y restauración de un objeto. Nada se borra.",
        },
        {
          src: "/diagrams/uml/comportamiento/estados-episodio-y-aprobacion.svg",
          caption: "Episodio de razonamiento y aprobación pendiente.",
        },
      ],
      basedOn: [
        "docs/uml/src/comportamiento/estados-objeto-cognitivo.puml",
        "docs/uml/src/comportamiento/estados-episodio-y-aprobacion.puml",
      ],
    },
    {
      id: "1.6",
      slug: "componentes",
      title: "Diagrama de componentes",
      status: "existing",
      description:
        "Los servicios que se ven desde fuera y, en más detalle, las piezas internas del servicio de memoria.",
      svgs: [
        {
          src: "/diagrams/uml/estructura/componentes.svg",
          caption: "Dashboard, Gateway, memoria, agentes, comunicaciones y la infraestructura que usan.",
        },
        {
          src: "/diagrams/uml/estructura/c4-componentes-memory.svg",
          caption: "Rutas, servicios y adaptadores dentro del servicio de memoria.",
        },
      ],
      basedOn: [
        "docs/uml/src/estructura/componentes.puml",
        "docs/uml/src/estructura/c4-componentes-memory.puml",
      ],
    },
    {
      id: "1.7",
      slug: "despliegue",
      title: "Diagrama de despliegue",
      status: "existing",
      description:
        "Dónde corre cada pieza en el servidor: contenedores, red interna, base de datos y los puertos que se publican.",
      svgs: [
        {
          src: "/diagrams/uml/estructura/despliegue.svg",
          caption: "Contenedores del compose, volúmenes, navegador y estación de trabajo.",
        },
      ],
      basedOn: ["docs/uml/src/estructura/despliegue.puml"],
    },
    {
      id: "1.8",
      slug: "objetos",
      title: "Diagrama de objetos",
      status: "generated",
      description:
        "Una foto de ejemplo, con los mismos campos que guarda Postgres: una decisión con dos versiones, la fuente de la captura, la nota que la respalda y la relación EVIDENCES entre ambas.",
      mermaid: `classDiagram
    direction LR
    class nodo["nodo : DbCognitiveObject"]
    class v1["v1 : DbObjectVersion"]
    class v2["v2 : DbObjectVersion"]
    class fuente["fuente : DbSource"]
    class evidencia["evidencia : DbCognitiveObject"]
    class enlace["enlace : DbCognitiveRelation"]

    nodo --> v1 : "version 1"
    nodo --> v2 : "version 2"
    v2 --> v1 : parent_version_id
    v1 --> fuente : source_id
    v2 --> fuente : source_id
    enlace --> evidencia : source_id
    enlace --> nodo : target_id

    note for nodo "knowledge_nodes. id 01932a10-7c3e-7a00-8000-0000000000a1. object_type decision. created_at 2026-07-21."
    note for v1 "knowledge_node_versions. version 1. title Usar Postgres con pgvector. status active. confidence 0.7. importance 0.8. salience 0.5. author usuario. parent_version_id nulo. embedding presente, 768 dimensiones. tombstoned_at nulo."
    note for v2 "version 2, la vigente. title Migraciones hasta el Thinking Graph. status active. confidence 0.9. parent_version_id 01932a10-7c3e-7a00-8000-0000000000b1. source_id el de la fuente."
    note for fuente "sources. id 01932a10-7c3e-7a00-8000-0000000000c1. kind cli. uri cli:nota-postgres. raw_ref nota-postgres. captured_at 2026-07-21. metadata vacío."
    note for evidencia "Otro knowledge_nodes. id 01932a10-7c3e-7a00-8000-0000000000a2. object_type evidence. Es el otro extremo de la relación."
    note for enlace "relations. source_id el de evidencia, target_id el de la decisión, relation_type EVIDENCES, valid_from 2026-07-21, valid_to nulo."`,
      basedOn: [
        "memory/src/infrastructure/database/models.py",
        "schemas/mindos_schemas/domain/object_type.py",
        "schemas/mindos_schemas/domain/relation_type.py",
      ],
    },
    {
      id: "1.9",
      slug: "paquetes",
      title: "Diagrama de paquetes",
      status: "existing",
      description:
        "Cómo se agrupa el código de cada servicio Python. El Dashboard no tiene paquetes propios en este juego: sus tipos están en el diagrama de clases.",
      svgs: [
        {
          src: "/diagrams/uml/generated/python/packages_memory.svg",
          caption: "Paquetes del servicio de memoria.",
        },
        {
          src: "/diagrams/uml/generated/python/packages_agents.svg",
          caption: "Paquetes del servicio de agentes.",
        },
        {
          src: "/diagrams/uml/generated/python/packages_gateway.svg",
          caption: "Paquetes del Gateway.",
        },
        {
          src: "/diagrams/uml/generated/python/packages_comms.svg",
          caption: "Paquetes de comunicaciones.",
        },
        {
          src: "/diagrams/uml/generated/python/packages_mcp_server.svg",
          caption: "Paquetes del servidor MCP.",
        },
        {
          src: "/diagrams/uml/generated/python/packages_common.svg",
          caption: "Paquetes compartidos de logging, ids y eventos.",
        },
        {
          src: "/diagrams/uml/generated/python/packages_schemas.svg",
          caption: "Paquetes de los contratos compartidos.",
        },
      ],
      basedOn: [
        "docs/uml/generated/python/packages_memory.puml",
        "docs/uml/generated/python/packages_agents.puml",
        "docs/uml/generated/python/packages_gateway.puml",
        "docs/uml/generated/python/packages_comms.puml",
        "docs/uml/generated/python/packages_mcp_server.puml",
        "docs/uml/generated/python/packages_common.puml",
        "docs/uml/generated/python/packages_schemas.puml",
      ],
    },
    {
      id: "1.10",
      slug: "estructura-compuesta",
      title: "Diagrama de estructura compuesta",
      status: "generated",
      description:
        "El interior del servicio de agentes tal como lo arma el arranque. La flecha continua es «usa» y la punteada es «cumple ese puerto». En el chat entra un solo asistente, Claude o el de demostración, y en el modelo entra uno de los tres adaptadores.",
      mermaid: `flowchart TB
    subgraph entradas ["Entradas"]
        router["assistant_router"]
        grafo["PlannerExecutorReviewerGraph"]
    end
    subgraph piezas ["Piezas que orquestan"]
        planner["LlmPlanner"]
        reviewer["LlmReviewer"]
        executor["CapabilityExecutor"]
        toolbox["AssistantToolbox"]
    end
    subgraph puertos ["Puertos"]
        pap["PersonalAgentPort"]
        csp["ConversationStorePort"]
        mgp["MemoryGatewayPort"]
        llp["LlmPort"]
        rrp["ReasoningRecorderPort"]
        ap["ApprovalPort"]
        crp["CapabilityRegistryPort"]
    end
    subgraph adaptadores ["Adaptadores"]
        claude["ClaudePersonalAgent"]
        demo["DemoPersonalAgent"]
        conv["InMemoryConversationStore"]
        httpmem["HttpMemoryGateway"]
        anth["AnthropicLlm"]
        oll["OllamaLlm"]
        mock["MockLlm"]
        rec["HttpReasoningRecorder"]
        noop["NoOpReasoningRecorder"]
        appr["InMemoryApprovalStore"]
        reg["InMemoryCapabilityRegistry"]
    end

    router --> pap
    router --> csp
    claude -.-> pap
    demo -.-> pap
    claude --> toolbox
    demo --> toolbox
    toolbox --> mgp
    httpmem -.-> mgp
    conv -.-> csp
    grafo --> planner
    grafo --> reviewer
    grafo --> executor
    grafo --> rrp
    planner --> llp
    reviewer --> llp
    anth -.-> llp
    oll -.-> llp
    mock -.-> llp
    executor --> crp
    executor --> ap
    rec -.-> rrp
    noop -.-> rrp
    appr -.-> ap
    reg -.-> crp`,
      basedOn: [
        "agents/src/main.py",
        "agents/src/api/assistant_router.py",
        "agents/src/domain/planner/agent_graph.py",
        "agents/src/domain/planner/llm_planner.py",
        "agents/src/domain/planner/llm_reviewer.py",
        "agents/src/domain/executor/capability_executor.py",
        "agents/src/application/assistant/toolbox.py",
        "agents/src/application/ports/personal_agent.py",
        "agents/src/application/ports/conversation_store.py",
        "agents/src/application/ports/memory_gateway.py",
        "agents/src/application/ports/llm.py",
        "agents/src/application/ports/reasoning_recorder.py",
        "agents/src/application/ports/approval.py",
        "agents/src/application/registry/capability_registry_port.py",
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/infrastructure/adapters/demo_personal_agent.py",
        "agents/src/infrastructure/adapters/http_memory_gateway.py",
        "agents/src/infrastructure/adapters/in_memory_conversation_store.py",
        "agents/src/infrastructure/adapters/anthropic_llm.py",
        "agents/src/infrastructure/adapters/ollama_llm.py",
        "agents/src/infrastructure/adapters/mock_llm.py",
        "agents/src/infrastructure/adapters/http_reasoning_recorder.py",
        "agents/src/infrastructure/adapters/noop_reasoning_recorder.py",
        "agents/src/infrastructure/adapters/in_memory_approval_store.py",
        "agents/src/infrastructure/adapters/in_memory_capability_registry.py",
      ],
    },
    {
      id: "1.11",
      slug: "perfiles",
      title: "Diagrama de perfiles",
      status: "generated",
      description:
        "Los cuatro estereotipos de la arquitectura hexagonal aplicados a clases que ya existen en agentes: puerto, adaptador, servicio y contrato de la API. No es un perfil UML publicado aparte: el código usa clases abstractas y modelos Pydantic.",
      mermaid: `classDiagram
    direction TB
    class PersonalAgentPort {
        <<port>>
        +stream_reply()
    }
    class MemoryGatewayPort {
        <<port>>
        +search_context()
        +ingest()
        +explain()
    }
    class LlmPort {
        <<port>>
        +generate()
        +chat()
    }
    class ReasoningRecorderPort {
        <<port>>
        +start_episode()
        +record_step()
        +close_episode()
    }
    class ClaudePersonalAgent {
        <<adapter>>
    }
    class HttpMemoryGateway {
        <<adapter>>
    }
    class AnthropicLlm {
        <<adapter>>
    }
    class OllamaLlm {
        <<adapter>>
    }
    class HttpReasoningRecorder {
        <<adapter>>
    }
    class NoOpReasoningRecorder {
        <<adapter>>
    }
    class LlmPlanner {
        <<service>>
        +plan()
    }
    class AssistantToolbox {
        <<service>>
        +execute()
    }
    class PlannerExecutorReviewerGraph {
        <<service>>
    }
    class AssistantChatRequest {
        <<dto>>
        +message
        +conversation_id
    }
    class ContextBundle {
        <<dto>>
        +query
        +fragments
    }

    PersonalAgentPort <|.. ClaudePersonalAgent
    MemoryGatewayPort <|.. HttpMemoryGateway
    LlmPort <|.. AnthropicLlm
    LlmPort <|.. OllamaLlm
    ReasoningRecorderPort <|.. HttpReasoningRecorder
    ReasoningRecorderPort <|.. NoOpReasoningRecorder
    ClaudePersonalAgent --> AssistantToolbox
    AssistantToolbox --> MemoryGatewayPort
    PlannerExecutorReviewerGraph --> ReasoningRecorderPort
    LlmPlanner --> LlmPort
    HttpMemoryGateway ..> ContextBundle : "JSON de /memory/context"
    note for AssistantChatRequest "Cuerpo de POST /api/v1/agents/assistant/chat. Lo lee assistant_router."`,
      basedOn: [
        "agents/src/application/ports/personal_agent.py",
        "agents/src/application/ports/memory_gateway.py",
        "agents/src/application/ports/llm.py",
        "agents/src/application/ports/reasoning_recorder.py",
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/infrastructure/adapters/http_memory_gateway.py",
        "agents/src/infrastructure/adapters/anthropic_llm.py",
        "agents/src/infrastructure/adapters/ollama_llm.py",
        "agents/src/infrastructure/adapters/http_reasoning_recorder.py",
        "agents/src/infrastructure/adapters/noop_reasoning_recorder.py",
        "agents/src/application/assistant/toolbox.py",
        "agents/src/domain/planner/llm_planner.py",
        "agents/src/domain/planner/agent_graph.py",
        "schemas/mindos_schemas/api/v1/assistant_dto.py",
        "schemas/mindos_schemas/api/v1/memory_dto.py",
      ],
    },
    {
      id: "1.12",
      slug: "comunicacion",
      title: "Diagrama de comunicación",
      status: "generated",
      description:
        "Un turno del asistente en el que Claude pide buscar en la memoria. Los números son el orden. Agents llama a Memory directo. El Gateway solo autentica y deja pasar el stream.",
      mermaid: `flowchart LR
    dash["Dashboard"]
    gw["Gateway"]
    ag["Agents"]
    mem["Memory"]
    claude["API de Claude"]

    dash -->|"1. POST /api/v1/agents/assistant/chat con JWT"| gw
    gw -->|"2. Proxy del POST, Accept event-stream"| ag
    ag -->|"3. SSE conversation"| gw
    gw -->|"4. Reenvía el evento"| dash
    ag -->|"5. messages.stream, modelo claude-sonnet-5-5"| claude
    claude -->|"6. tool_use search_memory"| ag
    ag -->|"7. POST /api/v1/memory/context"| mem
    mem -->|"8. Fragmentos de ContextBundle"| ag
    ag -->|"9. tool_result"| claude
    claude -->|"10. Deltas de texto"| ag
    ag -->|"11. SSE text y luego done"| gw
    gw -->|"12. El stream sigue hasta done"| dash`,
      basedOn: [
        "dashboard/src/lib/assistant-client.ts",
        "gateway/src/main.py",
        "agents/src/api/assistant_router.py",
        "agents/src/main.py",
        "agents/src/config.py",
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/infrastructure/adapters/http_memory_gateway.py",
        "agents/src/application/assistant/toolbox.py",
        "memory/src/main.py",
      ],
    },
    {
      id: "1.13",
      slug: "tiempos",
      title: "Diagrama de tiempos",
      status: "generated",
      description:
        "La misma charla, en una línea de tiempo. Las barras están en milisegundos aproximados, no medidos: primero la entrada, luego Claude pide buscar, Memory arma el contexto y el texto vuelve en vivo hasta el cierre.",
      mermaid: `gantt
    title Turno del asistente en milisegundos aproximados
    dateFormat x
    axisFormat %S
    section Entrada
    El navegador envía el mensaje :t1, 0, 40
    El Gateway valida la sesión y abre el proxy :t2, 40, 110
    Agents anuncia la conversacion :t3, 110, 150
    section Modelo
    Claude decide buscar en la memoria :t4, 150, 1100
    section Memoria
    Memory arma el contexto citable :t5, 1100, 1700
    section Respuesta
    Claude redacta y el texto llega en vivo :t6, 1700, 3400
    Agents cierra el turno con done :t7, 3400, 3460`,
      basedOn: [
        "dashboard/src/lib/assistant-client.ts",
        "gateway/src/main.py",
        "agents/src/api/assistant_router.py",
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/application/assistant/toolbox.py",
        "agents/src/infrastructure/adapters/http_memory_gateway.py",
        "memory/src/main.py",
      ],
    },
    {
      id: "1.14",
      slug: "interacciones",
      title: "Diagrama global de interacciones",
      status: "generated",
      description:
        "El hilo principal, de la captura a la explicación. Consultar y explicar no ocurren solos al guardar: leen lo que la ingesta dejó. Si el mensaje era una pregunta, el pipeline además dispara una meta del agente.",
      mermaid: `flowchart TD
    captura["Captura por CLI, REST o WhatsApp"] --> evento["Comms publica com.mindos.communication.message.received en mindos.comms"]
    evento --> pipeline["IngestionPipelineService"]
    pipeline --> medios["Si hay imagen o audio, guarda el archivo y extrae el texto"]
    medios --> ingesta["POST /api/v1/memory/ingest"]
    ingesta --> enlace["Si hay parecido real, POST /api/v1/memory/relation"]
    enlace --> guardado["Queda un nodo con versión y fuente"]
    pipeline --> agente["Si el texto pide respuesta, POST /api/v1/agents/execute"]
    guardado --> consulta["Consulta posterior, POST /api/v1/memory/context"]
    agente --> consulta
    consulta --> explicacion["GET /api/v1/thinking/explain/node_id"]`,
      basedOn: [
        "comms/src/config.py",
        "comms/src/infrastructure/adapters/event_bus_inbound_handler.py",
        "schemas/mindos_schemas/events/v1/communication_events.py",
        "memory/src/main.py",
        "memory/src/application/services/ingestion_pipeline.py",
        "memory/src/application/services/context_builder.py",
        "memory/src/application/services/explainability.py",
        "memory/src/api/thinking_router.py",
        "agents/src/main.py",
      ],
    },
  ],
};
