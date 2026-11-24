import type { DiagramCategory } from "./types";

export const seguridad: DiagramCategory = {
  id: "7",
  slug: "seguridad",
  title: "Seguridad",
  summary:
    "Muestra quién puede entrar, qué le está permitido y por dónde pasa lo que la persona guarda.",
  diagrams: [
    {
      id: "7.1",
      slug: "modelado-de-amenazas",
      title: "Diagrama de modelado de amenazas",
      status: "generated",
      description:
        "Amenazas visibles en el código, agrupadas por componente. Recoge suplantación, manipulación, repudio, divulgación, denegación y elevación solo donde hay un hecho concreto que contar.",
      basedOn: [
        "gateway/src/main.py",
        "gateway/src/config.py",
        "gateway/src/application/services/security.py",
        "dashboard/src/lib/auth.tsx",
        "dashboard/public/sw.js",
        "infra/docker-compose.yml",
        "mcp_server/mindos_mcp/auth_middleware.py",
        "agents/src/application/assistant/toolbox.py",
        "agents/src/domain/executor/capability_executor.py",
        "plan/08-asistente-personal-claude.md",
      ],
      mermaid: `flowchart TB
  nav["Navegador<br/>Suplantación: el JWT de localStorage es la sesión durante 24 h<br/>Divulgación: token, id de conversación y capturas pendientes quedan en el dispositivo<br/>Denegación: sin red se sirve la cáscara cacheada, no la memoria"]
  borde["Traefik<br/>Divulgación: TLS, con certificado público o el autofirmado<br/>Denegación: el host solo publica 80 y 443, y 80 redirige a HTTPS<br/>Elevación: es el único servicio con puertos hacia fuera"]
  gw["Gateway<br/>Suplantación: el JWT y la clave de servicio abren las mismas rutas<br/>Repudio: cada respuesta lleva X-Correlation-Id, sin un diario de lecturas<br/>Denegación: 120 peticiones por minuto. Si Redis falla, deja pasar<br/>Elevación: una credencial válida alcanza todo el proxy, aprobaciones incluidas"]
  red["Servicios de la red interna<br/>Divulgación: Memory y Agents no piden credencial en su puerto<br/>Manipulacion: el asistente puede guardar y no tiene herramienta para borrar<br/>Elevación: una capacidad con requires_approval espera a la persona"]
  mcpn["MCP<br/>Suplantación: clave propia en HTTP. En stdio basta controlar el proceso<br/>Divulgación: sus herramientas buscan, capturan y explican"]
  fuera["Proveedores<br/>Divulgación: con clave de Claude salen la pregunta, los fragmentos, las respuestas y el razonamiento<br/>Ollama, en el host, recibe el texto de embeddings y de contradicciones"]`,
    },
    {
      id: "7.2",
      slug: "limites-de-confianza",
      title: "Diagrama de límites de confianza",
      status: "generated",
      description:
        "Dónde cambia la confianza. Traefik es el único publicado y enruta solo al Gateway. Dentro de la red, Agents habla con Memory sin pasar por esa puerta. Claude y Ollama quedan fuera de los contenedores.",
      basedOn: [
        "infra/docker-compose.yml",
        "gateway/src/main.py",
        "gateway/src/config.py",
        "agents/src/infrastructure/adapters/http_memory_gateway.py",
        "agents/src/config.py",
        "mcp_server/mindos_mcp/server.py",
        "mcp_server/mindos_mcp/config.py",
        "memory/src/main.py",
      ],
      mermaid: `flowchart TB
  browser["Navegador"]
  wa["Servidores de WhatsApp"]
  claude["API de Claude"]
  ollama["Ollama en el host"]
  subgraph publicado ["Publicado al host"]
    traefik["Traefik: 80, 443 y TLS"]
  end
  subgraph red ["mindos-net, sin puertos propios"]
    gw["Gateway"]
    mem["Memory"]
    ag["Agents"]
    comms["Comms"]
    wab["Adaptador WhatsApp"]
    mcpn["MCP"]
    pg["Postgres"]
    rd["Redis"]
  end
  browser --> traefik --> gw
  gw --> mem
  gw --> ag
  gw --> comms
  gw --> mcpn
  gw -->|"límite por IP"| rd
  ag -->|"directo, sin Gateway"| mem
  ag --> claude
  ag --> ollama
  mem --> ollama
  mem --> pg
  comms --> rd
  wab --> comms
  wab --> wa
  mcpn -->|"clave de servicio"| gw`,
    },
    {
      id: "7.3",
      slug: "arbol-de-ataque",
      title: "Árbol de ataque",
      status: "generated",
      description:
        "Caminos distintos para leer la memoria, según las credenciales y la red que ya existen. Basta uno. El de la red interna solo empieza dentro de mindos-net, porque Traefik no publica Memory.",
      basedOn: [
        "gateway/src/main.py",
        "gateway/src/config.py",
        "dashboard/src/lib/auth.tsx",
        "infra/docker-compose.yml",
        "agents/src/infrastructure/adapters/http_memory_gateway.py",
        "mcp_server/mindos_mcp/server.py",
        "mcp_server/mindos_mcp/auth_middleware.py",
        "mcp_server/README.md",
      ],
      mermaid: `flowchart TD
  meta["Leer la memoria de la persona"]
  meta --> jwt["Tener el JWT del navegador"]
  meta --> clave["Tener la clave de servicio"]
  meta --> red["Estar en la red interna"]
  meta --> mcpn["Usar el cliente MCP"]
  jwt --> bearer["El Gateway acepta Authorization Bearer"]
  clave --> apikey["El Gateway acepta X-Api-Key"]
  bearer --> proxy["El proxy reenvía la lectura a Memory"]
  apikey --> proxy
  red --> muro["Traefik no publica Memory"]
  muro --> directo["Memory responde en su puerto sin credencial"]
  mcpn --> stdio["stdio: quien controla el proceso local"]
  mcpn --> http["HTTP: la clave propia del MCP"]
  stdio --> busca["mindos_search o mindos_context"]
  http --> busca
  busca --> clave`,
    },
    {
      id: "7.4",
      slug: "autenticacion",
      title: "Diagrama de autenticación",
      status: "generated",
      description:
        "Cómo se crea la sesión de la persona y cómo una llamada posterior entra con el token o con la clave de servicio. Las dos credenciales las comprueba el Gateway antes de reenviar. Un hash de contraseña vacío no coincide nunca.",
      basedOn: [
        "gateway/src/main.py",
        "gateway/src/application/services/security.py",
        "gateway/src/config.py",
        "gateway/src/application/ports/rate_limiter.py",
        "dashboard/src/lib/auth.tsx",
        "dashboard/src/lib/api-client.ts",
        "dashboard/src/app/login/page.tsx",
      ],
      mermaid: `sequenceDiagram
  actor Persona
  participant Dash as Dashboard
  participant GW as Gateway
  participant Down as Servicio interno
  participant Cliente as Cliente con clave
  Persona->>Dash: Usuario y contraseña
  Dash->>GW: POST /api/v1/auth/login
  Note over GW: Cuenta la petición por IP antes de la ruta
  GW->>GW: verify_password con Argon2id
  alt Coinciden con el único usuario
    GW-->>Dash: access_token, vence a las 24 h
    Dash->>Dash: Guarda mindos_session
  else No coinciden
    GW-->>Dash: 401 Usuario o contraseña incorrectos
  end
  Dash->>GW: Llamada con Authorization Bearer
  GW->>GW: decode_access_token, HS256
  GW->>Down: Proxy si el token trae sub
  Down-->>Dash: Respuesta
  Cliente->>GW: Llamada con X-Api-Key
  GW->>Down: Si la clave coincide, la identidad es service
  Down-->>Cliente: Respuesta
  Note over GW,Down: Si pasa de 120 en un minuto, responde 429. Si Redis falla, deja pasar`,
    },
    {
      id: "7.5",
      slug: "autorizacion",
      title: "Diagrama de autorización",
      status: "generated",
      description:
        "El Gateway solo separa quien trae credencial de quien no. No elige permisos según la identidad. Aparte, una capacidad marcada para aprobación humana se queda en espera hasta que la persona aprueba o rechaza. Las herramientas del asistente no usan esa pausa.",
      basedOn: [
        "gateway/src/main.py",
        "gateway/src/config.py",
        "agents/src/domain/executor/capability_executor.py",
        "agents/src/api/approvals_router.py",
        "agents/src/application/ports/approval.py",
        "agents/src/application/assistant/toolbox.py",
        "schemas/mindos_schemas/capabilities.py",
        "dashboard/src/app/(dashboard)/approvals/page.tsx",
      ],
      mermaid: `flowchart TD
  subgraph puerta ["Gateway"]
    req["Llega una petición"] --> cupo{"Cabe en el límite por IP"}
    cupo -->|no| muchas["429 Demasiadas peticiones"]
    cupo -->|si| ruta{"Qué ruta es"}
    ruta -->|"/health o el login"| abierta["Sigue sin credencial"]
    ruta -->|"Ruta del proxy"| cred{"JWT válido o clave de servicio"}
    cred -->|no| denegada["401 Credenciales inválidas o ausentes"]
    cred -->|si| proxy["Entra. La identidad no filtra la ruta"]
  end
  proxy --> lectura["Buscar, grafo, tiempo o explicar: responde"]
  proxy --> asistente["Pregunta al asistente: sus herramientas corren"]
  proxy --> ejecutor["El grafo de agentes mira la capacidad"]
  ejecutor --> bandera{"requires_approval"}
  bandera -->|no| corre["Ejecuta la capacidad"]
  bandera -->|si| espera["pending_approval, sin llamar al destino"]
  espera --> persona{"La persona en Aprobaciones"}
  persona -->|aprueba| corre
  persona -->|rechaza| quieta["La capacidad no se ejecuta"]`,
    },
    {
      id: "7.6",
      slug: "identidades-y-accesos",
      title: "Diagrama de identidades y accesos (IAM)",
      status: "generated",
      description:
        "Las identidades que el código distingue y con qué secreto se presentan. La persona es la única cuenta. El asistente no inicia sesión: llama a Memory por la red interna y usa su clave solo hacia Claude.",
      basedOn: [
        "gateway/src/main.py",
        "gateway/src/config.py",
        "gateway/src/application/services/security.py",
        "dashboard/src/lib/auth.tsx",
        "mcp_server/mindos_mcp/config.py",
        "mcp_server/mindos_mcp/auth_middleware.py",
        "mcp_server/mindos_mcp/server.py",
        "mcp_server/README.md",
        "agents/src/infrastructure/adapters/http_memory_gateway.py",
        "agents/src/config.py",
        "agents/src/main.py",
      ],
      mermaid: `flowchart TB
  persona["Persona administradora<br/>Un solo usuario, MINDOS_ADMIN_USERNAME<br/>La contraseña se comprueba con Argon2id<br/>El JWT lleva sub, iat y exp, y vive en el navegador"]
  servicio["Servicios<br/>X-Api-Key igual a MINDOS_API_KEY<br/>El Gateway los nombra service<br/>El servidor MCP llama así al Gateway"]
  cliente["Cliente MCP<br/>En HTTP presenta MCP_API_KEY<br/>En stdio no hay clave propia: manda el proceso local<br/>Desde fuera, el token va al Gateway y esta clave al MCP"]
  agente["Asistente<br/>No inicia sesión en el Gateway<br/>Llama a Memory por la URL interna<br/>ANTHROPIC_API_KEY solo sirve hacia Claude"]
  persona -->|"Authorization Bearer"| gw["Gateway"]
  servicio -->|"X-Api-Key"| gw
  cliente -->|"desde fuera, token más su clave"| gw
  cliente -->|"en la red interna, su clave"| mcpn["MCP"]
  mcpn --> servicio
  agente -->|"sin credencial de MindOS"| mem["Memory"]
  agente -->|"clave de Claude"| claude["API de Claude"]`,
    },
    {
      id: "7.7",
      slug: "roles-y-permisos",
      title: "Diagrama de roles y permisos (RBAC)",
      status: "generated",
      description:
        "Permisos de cada principal que el código ya distingue. La persona y la clave de servicio alcanzan las mismas rutas del proxy. El cliente MCP y el asistente tienen listas cerradas de herramientas, ambas sin borrar.",
      basedOn: [
        "gateway/src/main.py",
        "gateway/src/config.py",
        "mcp_server/mindos_mcp/server.py",
        "agents/src/application/assistant/toolbox.py",
        "agents/src/api/approvals_router.py",
        "dashboard/src/lib/auth.tsx",
        "dashboard/src/app/(dashboard)/approvals/page.tsx",
      ],
      mermaid: `flowchart TB
  anon["Sin credencial<br/>GET /health<br/>POST /api/v1/auth/login"]
  persona["Persona con JWT<br/>Menú completo<br/>Cualquier ruta del proxy<br/>Aprobar o rechazar<br/>Cerrar sesión en este navegador"]
  servicio["Clave de servicio<br/>Las mismas rutas del proxy<br/>También resolver aprobaciones<br/>Sin sesión de navegador"]
  cliente["Cliente MCP ya admitido<br/>mindos_search y mindos_context<br/>mindos_ingest<br/>mindos_ask_cognitive y mindos_explain"]
  agente["Asistente<br/>search_memory y save_memory<br/>list_decisions y find_contradictions<br/>recall_past_thinking<br/>explain_knowledge y get_history<br/>Sin herramienta de borrar ni archivar"]`,
    },
    {
      id: "7.8",
      slug: "flujo-de-datos-sensibles",
      title: "Diagrama de flujo de datos sensibles",
      status: "generated",
      description:
        "Por dónde pasan la contraseña, el token, las claves y el contenido de la memoria. A Claude salen la pregunta, los fragmentos recuperados, las respuestas y el razonamiento del asistente. Los embeddings y las contradicciones se quedan en Ollama, en el host.",
      basedOn: [
        "gateway/src/application/services/security.py",
        "gateway/src/config.py",
        "dashboard/src/lib/auth.tsx",
        "dashboard/src/lib/offline-queue.ts",
        "dashboard/public/sw.js",
        "dashboard/src/app/(dashboard)/capture/page.tsx",
        "comms/src/main.py",
        "memory/src/application/services/ingestion_pipeline.py",
        "memory/src/main.py",
        "agents/src/infrastructure/adapters/http_memory_gateway.py",
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "agents/src/application/assistant/toolbox.py",
        "plan/08-asistente-personal-claude.md",
        "infra/docker-compose.yml",
      ],
      mermaid: `flowchart LR
  env["Entorno del servidor<br/>hash Argon2id, JWT_SECRET y claves"]
  persona["Persona"] -->|"contraseña, solo al entrar"| gw["Gateway"]
  env --> gw
  gw -->|"JWT 24 h"| nav["Navegador<br/>mindos_session y id de conversación"]
  nav -->|"Bearer"| gw
  persona -->|"pregunta, nota o archivo"| gw
  movil["Compartir o captura sin red"] --> aparato["Cache o IndexedDB del teléfono"]
  aparato --> gw
  gw --> comms["Comms"]
  comms --> pipe["Pipeline de ingesta"]
  pipe --> mem["Memory"]
  mem --> pg["Postgres"]
  mem -->|"embeddings y contradicciones"| ollama["Ollama en el host"]
  ag["Agents"] -->|"herramientas, llamada directa"| mem
  env --> ag
  ag --> clave{"Hay clave de Claude"}
  clave -->|si| claude["API de Claude<br/>pregunta, fragmentos, respuestas y razonamiento"]
  clave -->|no| demo["Modo demostración<br/>busca en Memory y no llama a Claude"]
  demo --> mem`,
    },
  ],
};
