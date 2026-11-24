import type { DiagramCategory } from "./types";

export const procesos: DiagramCategory = {
  id: "4",
  slug: "procesos",
  title: "Procesos y lógica",
  summary:
    "Sirve para seguir un recorrido concreto, desde una nota de WhatsApp o una pregunta al asistente hasta lo que queda guardado.",
  diagrams: [
    {
      id: "4.1",
      slug: "procesos-de-negocio",
      title: "Diagrama de procesos de negocio (BPMN)",
      status: "generated",
      description:
        "El recorrido de una nota enviada por WhatsApp hasta quedar guardada como conocimiento con versión. Reacciones y recibos no se capturan. Si el texto resulta ser una pregunta, Memory pide después una respuesta al servicio de agentes.",
      basedOn: [
        "whatsapp/src/index.js",
        "whatsapp/src/comms_client.js",
        "whatsapp/src/message_utils.js",
        "comms/src/main.py",
        "comms/src/infrastructure/adapters/event_bus_inbound_handler.py",
        "memory/src/application/services/ingestion_pipeline.py",
        "memory/src/main.py",
      ],
      mermaid: `flowchart TB
  subgraph dueno ["Dueño"]
    m1["Escribe una nota o manda un archivo por WhatsApp"]
  end
  subgraph canal ["WhatsApp"]
    m2["Entrega el mensaje al puente"]
  end
  subgraph puente ["Puente Baileys"]
    m3["Ignora lo que no tiene texto ni archivo"]
    m4["Si hay archivo, lo descarga"]
    m5["POST /api/v1/comms/inbound"]
  end
  subgraph comms ["Comms"]
    m6["Publica message.received en mindos.comms"]
  end
  subgraph redis ["Redis"]
    m7["El stream conserva el evento"]
  end
  subgraph memoria ["Memory"]
    m8{"¿Hay archivo adjunto?"}
    m9["Guarda el archivo y extrae el texto"]
    m10{"¿Quedó texto?"}
    m11["POST /api/v1/memory/ingest"]
    m12["Queda un nodo con versión"]
    m13["Se descarta"]
  end
  m1 --> m2 --> m3 --> m4 --> m5 --> m6 --> m7 --> m8
  m8 -->|sí| m9 --> m10
  m8 -->|no| m10
  m10 -->|sí| m11 --> m12
  m10 -->|no| m13`,
    },
    {
      id: "4.2",
      slug: "flujo-de-datos",
      title: "Diagrama de flujo de datos (DFD)",
      status: "generated",
      description:
        "Los datos de primer nivel: qué entra desde la persona y desde fuera, qué proceso lo transforma y dónde se guarda. El Gateway no aparece porque no transforma el conocimiento. Solo deja pasar las llamadas del Dashboard.",
      basedOn: [
        "plan/README.md",
        "comms/src/main.py",
        "memory/src/main.py",
        "memory/src/application/services/ingestion_pipeline.py",
        "agents/src/main.py",
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "whatsapp/src/index.js",
      ],
      mermaid: `flowchart LR
  dueno["Dueño"]
  whatsapp["WhatsApp"]
  claude["API de Claude"]
  ollama["Ollama"]
  p1["1 Capturar el mensaje"]
  p2["2 Guardar en la memoria"]
  p3["3 Consultar y razonar"]
  p4["4 Avisar por el canal"]
  d1[("Conocimiento<br/>PostgreSQL")]
  d2[("Eventos<br/>Redis Streams")]
  d3[("Adjuntos")]
  dueno -->|notas y preguntas| p3
  dueno -->|mensajes| whatsapp
  whatsapp -->|mensaje| p1
  p1 -->|message.received| d2
  d2 -->|evento entrante| p2
  p2 -->|nodo y versión| d1
  p2 -->|archivo| d3
  p2 -->|texto a vectorizar| ollama
  ollama -->|embedding| p2
  p3 -->|lectura| d1
  d1 -->|fragmentos| p3
  p3 -->|consulta| claude
  claude -->|respuesta| p3
  p3 -->|respuesta| dueno
  p2 -->|si es pregunta| p3
  p3 -->|aviso| p4
  p4 -->|texto| whatsapp`,
    },
    {
      id: "4.3",
      slug: "diagrama-de-flujo",
      title: "Diagrama de flujo (Flowchart)",
      status: "generated",
      description:
        "El bucle del asistente: pide una respuesta a Claude, y si el modelo llama herramientas las ejecuta todas juntas y vuelve a preguntar. Si algo falla, el turno se deshace y la conversación queda como estaba. Un JSON de herramienta ilegible se reintenta, como mucho dos veces, antes de ese cierre.",
      basedOn: [
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/application/assistant/toolbox.py",
        "agents/src/application/ports/personal_agent.py",
      ],
      mermaid: `flowchart TD
  inicio["Llega el mensaje de la persona"] --> stream["Pide un stream a la API de Claude"]
  stream --> llamada{"¿La llamada respondió?"}
  llamada -->|no| fallo["Deshace el turno y avisa del error"]
  llamada -->|sí| motivo{"¿Por qué paró el modelo?"}
  motivo -->|rechazo| fallo
  motivo -->|pausa del turno| stream
  motivo -->|sin herramientas| cierre["Guarda el texto y cierra el turno"]
  motivo -->|pide herramientas| corte{"¿La herramienta llegó cortada?"}
  corte -->|sí| fallo
  corte -->|no| rondas{"¿Ya van demasiadas rondas?"}
  rondas -->|sí| fallo
  rondas -->|no| ejecuta["Ejecuta las herramientas en paralelo"]
  ejecuta --> resultados["Devuelve todos los resultados en un solo mensaje"]
  resultados --> stream`,
    },
    {
      id: "4.4",
      slug: "diagrama-de-carriles",
      title: "Diagrama de carriles (Swimlane)",
      status: "generated",
      description:
        "Qué pasa cuando una acción del agente necesita un sí de la persona. El razonamiento se detiene, la bandeja muestra la pendiente y, al resolverla, queda anotado en la traza si se ejecutó o se rechazó.",
      basedOn: [
        "agents/src/domain/executor/capability_executor.py",
        "agents/src/domain/planner/agent_graph.py",
        "agents/src/api/approvals_router.py",
        "agents/src/application/ports/approval.py",
        "dashboard/src/lib/api-client.ts",
        "comms/src/main.py",
      ],
      mermaid: `flowchart TB
  subgraph agentes ["Agents"]
    a1["La capacidad pide aprobación"]
    a2["Guarda la aprobación como pendiente"]
    a3{"¿Había canal de origen?"}
    a4["Pide a Comms avisar por ese canal"]
    a5["El grafo se detiene"]
    a8{"¿La persona aprueba?"}
    a9["Ejecuta la capacidad con los datos originales"]
    a10["No ejecuta nada"]
    a11["Anota el paso y cierra el episodio"]
  end
  subgraph dueno ["Dueño"]
    d1["Revisa la bandeja y decide"]
  end
  subgraph entrada ["Dashboard y Gateway"]
    g1["GET /api/v1/approvals/"]
    g2["POST /api/v1/approvals/id/resolve"]
  end
  subgraph memoria ["Memory"]
    mem1["Queda el paso y el cierre en la traza"]
  end
  a1 --> a2 --> a3
  a3 -->|sí| a4 --> a5
  a3 -->|no| a5
  a5 --> g1 --> d1 --> g2 --> a8
  a8 -->|sí| a9 --> a11
  a8 -->|no| a10 --> a11
  a11 --> mem1`,
    },
    {
      id: "4.5",
      slug: "arbol-de-decisiones",
      title: "Árbol de decisiones",
      status: "generated",
      description:
        "Las decisiones de una captura que llega por el bus. El pipeline siempre la guarda como nota y, si ya había algo casi igual, crea un nodo nuevo enlazado. La contradicción se comprueba dentro de la ingesta, pero con una nota no llega a ejecutarse: solo corre para fact o hypothesis.",
      basedOn: [
        "memory/src/application/services/ingestion_pipeline.py",
        "memory/src/main.py",
        "memory/src/application/services/contradiction_detector.py",
        "schemas/mindos_schemas/api/v1/memory_dto.py",
      ],
      mermaid: `flowchart TD
  evento["Llega message.received"] --> valido{"¿El evento se puede leer?"}
  valido -->|no| descarte1["Se descarta"]
  valido -->|sí| medio{"¿Trae archivo?"}
  medio -->|sí| extrae["Guarda el archivo y extrae el texto"]
  medio -->|no| texto["Usa el texto del mensaje"]
  extrae --> vacio
  texto --> vacio
  vacio{"¿Quedó texto?"} -->|no| descarte2["Se descarta"]
  vacio -->|sí| ingest["POST /api/v1/memory/ingest como note"]
  ingest --> dup{"¿Hay un nodo activo casi igual?"}
  dup -->|sí| enlace["Nodo nuevo y relación DUPLICATE_OF"]
  dup -->|no| nuevo["Nodo nuevo"]
  enlace --> tipo
  nuevo --> tipo
  tipo{"¿Es fact o hypothesis?"} -->|no| auto["Busca parecidos y propone un enlace"]
  tipo -->|sí| contra["El modelo confirma o descarta la contradicción"]
  contra --> auto
  auto --> pregunta{"¿El modelo dice que es una pregunta?"}
  pregunta -->|sí| agente["POST /api/v1/agents/execute"]
  pregunta -->|no| fin["Queda guardada"]
  agente --> fin`,
    },
    {
      id: "4.6",
      slug: "diagrama-sipoc",
      title: "Diagrama SIPOC",
      status: "generated",
      description:
        "La ingesta de un mensaje en una ficha: quién la alimenta, qué entra, qué pasos da, qué deja guardado y quién lo usa después. El aviso al bus sale igual, aunque hoy ningún otro servicio lo consuma.",
      basedOn: [
        "memory/src/application/services/ingestion_pipeline.py",
        "memory/src/main.py",
        "schemas/mindos_schemas/events/v1/communication_events.py",
        "schemas/mindos_schemas/events/v1/memory_events.py",
        "comms/src/main.py",
      ],
      mermaid: `flowchart LR
  subgraph proveedores ["Proveedores"]
    sDueno["Dueño"]
    sCanal["WhatsApp, CLI o REST"]
  end
  subgraph entradas ["Entradas"]
    iTexto["Texto del mensaje"]
    iArchivo["Archivo en base64, si lo hay"]
    iCanal["Canal, remitente e identificador"]
  end
  subgraph proceso ["Proceso"]
    p1["Resolver el archivo"]
    p2["Ingerir con dedup y versión"]
    p3["Proponer enlaces"]
    p4["Clasificar si es pregunta"]
  end
  subgraph salidas ["Salidas"]
    oNodo["Nodo con versión"]
    oEvento["Evento knowledge.created"]
    oRel["Relación DUPLICATE_OF o de enlace"]
  end
  subgraph clientes ["Clientes"]
    cDueno["El dueño, al buscar o preguntar"]
    cAgents["Agents, si era una pregunta"]
  end
  sDueno --> sCanal
  sCanal --> iTexto
  sCanal --> iArchivo
  sCanal --> iCanal
  iTexto --> p1
  iArchivo --> p1
  iCanal --> p1
  p1 --> p2 --> p3 --> p4
  p2 --> oNodo
  p2 --> oEvento
  p2 --> oRel
  p3 --> oRel
  oNodo --> cDueno
  p4 --> cAgents`,
    },
  ],
};
