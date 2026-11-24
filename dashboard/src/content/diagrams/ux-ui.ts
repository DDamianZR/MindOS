import type { DiagramCategory } from "./types";

export const uxUi: DiagramCategory = {
  id: "5",
  slug: "ux-ui",
  title: "UX/UI",
  summary:
    "Muestra cómo entra una persona, cómo está organizado el menú y cómo una captura acaba en una respuesta con fuentes.",
  diagrams: [
    {
      id: "5.1",
      slug: "user-flow",
      title: "User Flow",
      status: "generated",
      description:
        "Camino desde abrir MindOS hasta leer una respuesta del asistente y seguir una de sus fuentes. Si la sesión ya existía, el login se salta. Si venías de otra vista, al entrar vuelves a esa vista.",
      basedOn: [
        "dashboard/src/app/page.tsx",
        "dashboard/src/app/login/page.tsx",
        "dashboard/src/app/(dashboard)/layout.tsx",
        "dashboard/src/app/(dashboard)/assistant/page.tsx",
        "dashboard/src/lib/auth.tsx",
        "dashboard/src/lib/assistant-client.ts",
        "dashboard/src/components/assistant/AnswerProse.tsx",
        "dashboard/src/components/assistant/Marginalia.tsx",
      ],
      mermaid: `flowchart TD
  abrir["Abre MindOS"] --> sesion{"Hay sesión guardada"}
  sesion -->|no| login["Login: usuario y contraseña"]
  login --> ok{"Coinciden"}
  ok -->|no| aviso["Aviso de usuario o contraseña incorrectos"]
  aviso --> login
  ok -->|si| volver["Vuelve a la vista de origen o a Inicio"]
  sesion -->|si| asistente
  volver --> asistente["Asistente: pregunta o completa una frase"]
  asistente --> envia["Envía el mensaje"]
  envia --> vivo["Ve el estado: leyendo, pensando o la consulta en curso"]
  vivo --> respuesta["Lee la respuesta y las fuentes al margen"]
  respuesta --> cita["Abre una cita en Razonamiento"]
  vivo -->|falla o la detiene| reintento["Vuelve a intentar"]
  reintento --> envia`,
    },
    {
      id: "5.2",
      slug: "sitemap",
      title: "Sitemap",
      status: "generated",
      description:
        "Rutas del menú y de la entrada. La app instalada abre Capturar, y compartir desde otra app también llega ahí. Inicio, Rutinas y Diagramas están en el menú.",
      basedOn: [
        "dashboard/src/components/TopNav.tsx",
        "dashboard/src/app/page.tsx",
        "dashboard/src/app/login/page.tsx",
        "dashboard/src/app/(dashboard)/layout.tsx",
        "dashboard/src/app/manifest.ts",
        "dashboard/public/sw.js",
        "dashboard/src/app/api/share-target/route.ts",
        "dashboard/src/app/(dashboard)/assistant/page.tsx",
        "dashboard/src/app/(dashboard)/search/page.tsx",
        "dashboard/src/app/(dashboard)/graph/page.tsx",
        "dashboard/src/app/(dashboard)/timeline/page.tsx",
        "dashboard/src/app/(dashboard)/capture/page.tsx",
        "dashboard/src/app/(dashboard)/explain/page.tsx",
        "dashboard/src/app/(dashboard)/cognitive/page.tsx",
        "dashboard/src/app/(dashboard)/contradictions/page.tsx",
        "dashboard/src/app/(dashboard)/approvals/page.tsx",
      ],
      mermaid: `flowchart TD
  app["MindOS"] --> fuera["Sin sesión"]
  app --> dentro["Con sesión"]
  fuera --> portada["/ abre Inicio o Login"]
  fuera --> login["/login"]
  dentro --> inicio["/inicio Inicio"]
  dentro --> asistente["/assistant Asistente"]
  dentro --> memoria["Memoria"]
  memoria --> buscar["/search Buscar"]
  memoria --> grafo["/graph Grafo"]
  memoria --> tiempo["/timeline Línea de tiempo"]
  memoria --> capturar["/capture Capturar"]
  dentro --> pensamiento["Pensamiento"]
  pensamiento --> razonar["/explain Razonamiento"]
  pensamiento --> preguntas["/cognitive Siete preguntas"]
  pensamiento --> contras["/contradictions Contradicciones"]
  dentro --> agentes["Agentes"]
  agentes --> rutinas["/routines Rutinas"]
  agentes --> aprobaciones["/approvals Aprobaciones"]
  dentro --> diagramas["/diagrams Diagramas"]
  instalada["App instalada"] --> capturar
  compartir["Compartir desde otra app"] --> capturar`,
    },
    {
      id: "5.3",
      slug: "wireflow",
      title: "Wireflow",
      status: "generated",
      description:
        "Pantallas con lo que muestran y las acciones que saltan a otra. El menú abre cada sección. Las flechas sueltas son los saltos que hace la propia pantalla: entrar, citar, razonar, compartir y guardar sin red.",
      basedOn: [
        "dashboard/src/components/TopNav.tsx",
        "dashboard/src/app/login/page.tsx",
        "dashboard/src/app/(dashboard)/layout.tsx",
        "dashboard/src/app/(dashboard)/assistant/page.tsx",
        "dashboard/src/app/(dashboard)/search/page.tsx",
        "dashboard/src/app/(dashboard)/graph/page.tsx",
        "dashboard/src/app/(dashboard)/timeline/page.tsx",
        "dashboard/src/app/(dashboard)/capture/page.tsx",
        "dashboard/src/app/(dashboard)/explain/page.tsx",
        "dashboard/src/app/(dashboard)/cognitive/page.tsx",
        "dashboard/src/app/(dashboard)/contradictions/page.tsx",
        "dashboard/src/app/(dashboard)/approvals/page.tsx",
        "dashboard/src/components/NodeDetailPanel.tsx",
        "dashboard/src/components/assistant/Marginalia.tsx",
        "dashboard/public/sw.js",
        "dashboard/src/lib/offline-queue.ts",
      ],
      mermaid: `flowchart TD
  login["Login<br/>Usuario, contraseña y Entrar"] -->|"Entra"| menu["Menú"]
  menu --> asistente["Asistente<br/>Frases para empezar, respuesta y fuentes"]
  menu --> buscar["Buscar<br/>Consulta, resultados y ficha del nodo"]
  menu --> grafo["Grafo<br/>Vecinos a partir de un nodo"]
  menu --> tiempo["Línea de tiempo<br/>Versiones y un momento pasado"]
  menu --> capturar["Capturar<br/>Nota, archivo y pendientes de red"]
  menu --> razonar["Razonamiento<br/>Evidencia de un nodo o un episodio"]
  menu --> preguntas["Siete preguntas<br/>Seis consultas"]
  menu --> contras["Contradicciones<br/>Barrido general o un tema"]
  menu --> aprobaciones["Aprobaciones<br/>Aprobar o rechazar"]
  asistente -->|"Abre una cita"| razonar
  buscar -->|"Ver razonamiento"| razonar
  grafo -->|"Ver razonamiento"| razonar
  preguntas -->|"La séptima pregunta"| razonar
  compartir["Otra app comparte"] -->|"Llena el texto o el archivo"| capturar
  capturar -->|"Sin red"| cola["Queda en el teléfono"]
  cola -->|"Vuelve la red"| capturar`,
    },
    {
      id: "5.4",
      slug: "customer-journey-map",
      title: "Customer Journey Map",
      status: "generated",
      description:
        "Experiencia de guardar algo desde el móvil y recuperarlo semanas después preguntando. La espera sin red es el tramo menos cómodo. Encontrarlo citado es el tramo que cierra el recorrido.",
      basedOn: [
        "dashboard/src/app/manifest.ts",
        "dashboard/public/sw.js",
        "dashboard/src/app/api/share-target/route.ts",
        "dashboard/src/app/(dashboard)/capture/page.tsx",
        "dashboard/src/lib/offline-queue.ts",
        "dashboard/src/app/(dashboard)/assistant/page.tsx",
        "dashboard/src/components/assistant/Marginalia.tsx",
        "dashboard/src/components/ServiceWorkerRegistration.tsx",
      ],
      mermaid: `journey
    title Capturar en el móvil y recuperarlo después
    section Hoy
      Instalar la app y entrar: 3: Persona
      Compartir una nota o una foto: 5: Persona
      Verla lista en Capturar: 5: Persona
      Enviarla al volver la red: 4: Persona
    section Semanas después
      Preguntar por aquello: 5: Persona
      Leer la respuesta y abrir la cita: 5: Persona`,
    },
    {
      id: "5.5",
      slug: "service-blueprint",
      title: "Service Blueprint",
      status: "generated",
      description:
        "Una pregunta al asistente, en cuatro carriles: lo que hace la persona, lo que ve, lo que resuelven los servicios y lo que sostiene la respuesta. Con clave de Claude el texto sale a esa API. Sin clave, el asistente busca igual y responde en modo demostración.",
      basedOn: [
        "dashboard/src/app/(dashboard)/assistant/page.tsx",
        "dashboard/src/lib/assistant-client.ts",
        "dashboard/src/components/assistant/Marginalia.tsx",
        "gateway/src/main.py",
        "agents/src/application/assistant/toolbox.py",
        "agents/src/infrastructure/adapters/http_memory_gateway.py",
        "agents/src/infrastructure/adapters/claude_personal_agent.py",
        "plan/08-asistente-personal-claude.md",
        "infra/docker-compose.yml",
      ],
      mermaid: `flowchart TB
  subgraph persona ["Persona"]
    p1["Escribe o completa una frase"]
    p2["Lee la respuesta y las fuentes"]
    p3["Abre una cita"]
  end
  subgraph pantalla ["Lo que se ve"]
    f1["Compositor del Asistente"]
    f2["Texto en vivo y margen con fuentes"]
    f3["Razonamiento de ese nodo"]
  end
  subgraph servicios ["Servicios"]
    b1["Gateway comprueba la sesión y reenvía el flujo"]
    b2["El asistente consulta la memoria"]
    b3["Memory devuelve fragmentos citables"]
  end
  subgraph soporte ["Soporte"]
    s1["Postgres"]
    s2["Ollama en el host, para embeddings"]
    s3["API de Claude, si hay clave"]
    s4["Modo demostración, si no hay clave"]
  end
  p1 --> f1 --> b1 --> b2 --> b3
  b3 --> s1
  b3 --> s2
  b2 --> s3
  b2 --> s4
  b3 --> f2 --> p2
  p3 --> f3`,
    },
    {
      id: "5.6",
      slug: "storyboard",
      title: "Storyboard",
      status: "generated",
      description:
        "Viñetas, en orden, de guardar algo desde el móvil y volver a encontrarlo en una respuesta. Es el mismo recorrido que el mapa de experiencia, contado como escenas.",
      basedOn: [
        "dashboard/src/app/manifest.ts",
        "dashboard/public/sw.js",
        "dashboard/src/app/(dashboard)/capture/page.tsx",
        "dashboard/src/lib/offline-queue.ts",
        "dashboard/src/app/(dashboard)/assistant/page.tsx",
        "dashboard/src/components/assistant/AnswerProse.tsx",
        "dashboard/src/components/assistant/Marginalia.tsx",
      ],
      mermaid: `timeline
    title Capturar y volver a encontrarlo
    section En el momento
        Compartir : Otra app envía un texto, un enlace o un archivo
        Captura : La nota queda lista para guardar
        Sin red : Se queda en el teléfono y sale cuando vuelve la conexión
    section Semanas después
        Preguntar : El asistente busca en lo guardado
        Cita : La respuesta muestra de qué nota salió
        Seguir : La fuente abre el razonamiento de ese nodo`,
    },
    {
      id: "5.7",
      slug: "navegacion",
      title: "Diagrama de navegación",
      status: "generated",
      description:
        "Cómo se pasa de una vista a otra: el menú, el logo hacia Inicio, las citas y la ficha de un nodo hacia Razonamiento, y el regreso al login al cerrar sesión. La app instalada y compartir abren Capturar.",
      basedOn: [
        "dashboard/src/components/TopNav.tsx",
        "dashboard/src/app/page.tsx",
        "dashboard/src/app/login/page.tsx",
        "dashboard/src/app/(dashboard)/layout.tsx",
        "dashboard/src/lib/auth.tsx",
        "dashboard/src/app/manifest.ts",
        "dashboard/public/sw.js",
        "dashboard/src/components/assistant/AnswerProse.tsx",
        "dashboard/src/components/assistant/Marginalia.tsx",
        "dashboard/src/components/NodeDetailPanel.tsx",
        "dashboard/src/app/(dashboard)/cognitive/page.tsx",
      ],
      mermaid: `flowchart TD
  portada["/"] -->|sin sesión| login["Login"]
  portada -->|con sesión| inicio["Inicio"]
  login -->|"Entra"| inicio
  login -->|"Volvía de otra vista"| destino["Esa vista"]
  guard["Vista sin sesión"] -->|"Pide login y recuerda el destino"| login
  logo["Logo"] --> inicio
  inicio --> asistente["Asistente"]
  inicio --> buscar["Buscar"]
  inicio --> grafo["Grafo"]
  inicio --> tiempo["Línea de tiempo"]
  inicio --> capturar["Capturar"]
  inicio --> razonar["Razonamiento"]
  inicio --> preguntas["Siete preguntas"]
  inicio --> contras["Contradicciones"]
  inicio --> rutinas["Rutinas"]
  inicio --> aprobaciones["Aprobaciones"]
  inicio --> diagramas["Diagramas"]
  asistente -->|"Cita"| razonar
  buscar -->|"Ficha del nodo"| razonar
  grafo -->|"Ficha del nodo"| razonar
  preguntas -->|"La séptima pregunta"| razonar
  salir["Cerrar sesión"] --> login
  instalada["App instalada"] --> capturar
  compartir["Compartir"] --> capturar`,
    },
    {
      id: "5.8",
      slug: "arquitectura-de-informacion",
      title: "Diagrama de arquitectura de información",
      status: "generated",
      description:
        "Cómo está agrupado lo que la persona viene a hacer. El asistente añade la conversación y las fuentes. Capturar también es la puerta de la app instalada y de lo que se comparte desde el móvil.",
      basedOn: [
        "dashboard/src/components/TopNav.tsx",
        "dashboard/src/app/(dashboard)/assistant/page.tsx",
        "dashboard/src/components/assistant/Marginalia.tsx",
        "dashboard/src/app/manifest.ts",
        "dashboard/src/app/(dashboard)/capture/page.tsx",
        "dashboard/src/app/(dashboard)/cognitive/page.tsx",
      ],
      mermaid: `mindmap
  root((MindOS))
    Inicio
    Asistente
      ["Conversación"]
      Fuentes
    Memoria
      Buscar
      Grafo
      ["Línea de tiempo"]
      Capturar
        ["App instalada"]
        Compartir
    Pensamiento
      Razonamiento
      ["Siete preguntas"]
      Contradicciones
    Agentes
      Rutinas
      Aprobaciones
    Diagramas`,
    },
  ],
};
