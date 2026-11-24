import type { DiagramCategory } from "./types";

const basedOnSchema = [
  "memory/src/infrastructure/database/models.py",
  "memory/src/config.py",
  "memory/alembic/versions/0001_initial_schema.py",
  "memory/alembic/versions/0002_cognitive_fields.py",
  "memory/alembic/versions/0003_provenance.py",
  "memory/alembic/versions/0004_thinking_graph.py",
];

export const basesDeDatos: DiagramCategory = {
  id: "2",
  slug: "bases-de-datos",
  title: "Bases de datos",
  summary:
    "Muestra cómo quedan guardados el conocimiento versionado, su procedencia y el razonamiento del agente en Postgres.",
  diagrams: [
    {
      id: "2.1",
      slug: "entidad-relacion",
      title: "Diagrama entidad-relación (ERD)",
      status: "existing",
      description:
        "Las siete tablas actuales y cómo se enlazan. El dibujo ya incluye las fuentes de la migración 0003 y los episodios del Thinking Graph de la 0004, igual que los modelos.",
      svgs: [
        {
          src: "/diagrams/uml/estructura/er-base-de-datos.svg",
          caption: "Tablas, claves e índices de Alembic 0001 a 0004.",
        },
      ],
      basedOn: ["docs/uml/src/estructura/er-base-de-datos.puml", ...basedOnSchema],
    },
    {
      id: "2.2",
      slug: "esquema-relacional",
      title: "Diagrama de esquema relacional",
      status: "generated",
      description:
        "El mismo esquema con el tipo de cada columna, las claves y el nombre del índice que la acelera. La cita de un paso a un nodo vive en un JSON, sin clave foránea.",
      mermaid: `erDiagram
    direction TB
    knowledge_nodes ||--|{ knowledge_node_versions : versiones
    knowledge_node_versions |o--o{ knowledge_node_versions : parent_version_id
    sources |o--o{ knowledge_node_versions : procedencia
    knowledge_nodes ||--o{ relations : origen
    knowledge_nodes ||--o{ relations : destino
    reasoning_episodes ||--o{ reasoning_steps : pasos
    reasoning_steps }o--o{ knowledge_nodes : "knowledge_refs sin FK"

    knowledge_nodes {
        uuid id PK
        varchar object_type "varchar 50"
        timestamptz created_at
    }
    sources {
        uuid id PK
        varchar kind "varchar 30"
        text uri "índice ix_sources_kind_uri junto con kind"
        text raw_ref
        timestamptz captured_at
        jsonb metadata
    }
    knowledge_node_versions {
        uuid id PK
        uuid node_id FK "borra en cascada. índice parcial ix_versions_active si tombstoned_at es nulo"
        int version "único con node_id, uidx_node_version"
        varchar title "varchar 255"
        text content
        vector embedding "768 dimensiones. índice HNSW ix_versions_embedding, distancia coseno"
        jsonb metadata
        timestamptz created_at "índice ix_versions_created_at"
        varchar author "varchar 100"
        uuid parent_version_id FK
        float confidence
        float importance
        varchar status "varchar 20"
        jsonb evidence
        float salience
        timestamptz tombstoned_at
        uuid source_id FK
    }
    relations {
        uuid source_id PK, FK "borra en cascada. índice parcial ix_relations_source_active si valid_to es nulo"
        uuid target_id PK, FK "borra en cascada"
        varchar relation_type PK "varchar 50"
        timestamptz valid_from PK
        timestamptz valid_to
        jsonb metadata
    }
    knowledge_event_log {
        uuid event_id PK
        varchar event_type "varchar 100"
        jsonb payload
        timestamptz logged_at
    }
    reasoning_episodes {
        uuid id PK
        text goal
        uuid correlation_id "índice ix_reasoning_episodes_correlation"
        varchar agent "varchar 100"
        varchar status "varchar 20"
        timestamptz started_at
        timestamptz ended_at
        text final_output
    }
    reasoning_steps {
        uuid id PK
        uuid episode_id FK "borra en cascada. índice ix_reasoning_steps_episode"
        int step_index
        varchar kind "varchar 20"
        text input
        text output
        varchar capability_name "varchar 100"
        bool approved
        text feedback
        timestamptz created_at
        jsonb knowledge_refs "índice GIN ix_reasoning_steps_knowledge_refs, jsonb_path_ops"
    }`,
      basedOn: basedOnSchema,
    },
    {
      id: "2.3",
      slug: "modelo-conceptual",
      title: "Modelo conceptual de datos",
      status: "generated",
      description:
        "Las cosas que MindOS recuerda, sin tipos ni tablas: un objeto y sus versiones, de dónde salió, cómo se enlaza con otros, y el episodio en el que el agente pensó. El registro de eventos no apunta a nadie: solo anota lo que pasó.",
      mermaid: `classDiagram
    direction TB
    class ObjetoCognitivo["Objeto cognitivo"]
    class Version["Versión"]
    class Fuente["Fuente"]
    class Relacion["Relación"]
    class Episodio["Episodio de razonamiento"]
    class Paso["Paso de razonamiento"]
    class Registro["Registro de eventos"]

    ObjetoCognitivo "1" --> "*" Version : versiones
    Version "*" --> "0..1" Fuente : procedencia
    Version "*" --> "0..1" Version : "versión anterior"
    ObjetoCognitivo "1" --> "*" Relacion : origen
    ObjetoCognitivo "1" --> "*" Relacion : destino
    Episodio "1" --> "*" Paso : pasos
    Paso "*" --> "*" ObjetoCognitivo : "nodos citados"`,
      basedOn: [
        ...basedOnSchema,
        "schemas/mindos_schemas/domain/object_type.py",
        "schemas/mindos_schemas/domain/relation_type.py",
      ],
    },
    {
      id: "2.4",
      slug: "modelo-logico",
      title: "Modelo lógico de datos",
      status: "generated",
      description:
        "Atributos y relaciones del conocimiento, con tipos lógicos y sin detalles de Postgres. El vector tiene 768 números porque el embedding de MindOS es nomic-embed-text. Los nombres de columna son los de las tablas.",
      mermaid: `erDiagram
    direction TB
    OBJETO ||--|{ VERSION : versiones
    VERSION |o--o{ VERSION : "versión anterior"
    FUENTE |o--o{ VERSION : procedencia
    OBJETO ||--o{ RELACION : origen
    OBJETO ||--o{ RELACION : destino
    EPISODIO ||--o{ PASO : pasos
    PASO }o--o{ OBJETO : nodos_citados

    OBJETO {
        identificador id PK
        texto object_type
        fecha created_at
    }
    FUENTE {
        identificador id PK
        texto kind
        texto uri
        texto raw_ref
        fecha captured_at
        mapa metadata
    }
    VERSION {
        identificador id PK
        identificador node_id FK
        entero version "único junto con node_id"
        texto title
        texto content
        vector embedding "768 numeros"
        mapa metadata
        fecha created_at
        texto author
        identificador parent_version_id FK
        numero confidence
        numero importance
        texto status
        lista evidence
        numero salience
        fecha tombstoned_at
        identificador source_id FK
    }
    RELACION {
        identificador source_id PK, FK
        identificador target_id PK, FK
        texto relation_type PK
        fecha valid_from PK
        fecha valid_to
        mapa metadata
    }
    REGISTRO {
        identificador event_id PK
        texto event_type
        mapa payload
        fecha logged_at
    }
    EPISODIO {
        identificador id PK
        texto goal
        identificador correlation_id
        texto agent
        texto status
        fecha started_at
        fecha ended_at
        texto final_output
    }
    PASO {
        identificador id PK
        identificador episode_id FK
        entero step_index
        texto kind
        texto input
        texto output
        texto capability_name
        booleano approved
        texto feedback
        fecha created_at
        lista knowledge_refs
    }`,
      basedOn: [
        ...basedOnSchema,
        "schemas/mindos_schemas/domain/object_type.py",
        "schemas/mindos_schemas/domain/relation_type.py",
      ],
    },
    {
      id: "2.5",
      slug: "modelo-fisico",
      title: "Modelo físico de datos",
      status: "generated",
      description:
        "Cómo lo crea Alembic en Postgres 16 con pgvector. El embedding es vector de 768, el índice de búsqueda es HNSW con distancia coseno, y hay índices parciales y un GIN sobre las citas de cada paso.",
      mermaid: `erDiagram
    direction TB
    knowledge_nodes ||--|{ knowledge_node_versions : versiones
    knowledge_node_versions |o--o{ knowledge_node_versions : parent_version_id
    sources |o--o{ knowledge_node_versions : procedencia
    knowledge_nodes ||--o{ relations : origen
    knowledge_nodes ||--o{ relations : destino
    reasoning_episodes ||--o{ reasoning_steps : pasos
    reasoning_steps }o--o{ knowledge_nodes : "jsonb sin FK"

    knowledge_nodes {
        uuid id PK "uuid"
        varchar object_type "varchar 50, no es ENUM"
        timestamptz created_at "timestamptz default now"
    }
    sources {
        uuid id PK "uuid"
        varchar kind "varchar 30"
        text uri "text, opcional"
        text raw_ref "text, opcional"
        timestamptz captured_at "timestamptz default now"
        jsonb metadata "jsonb default objeto vacio"
    }
    knowledge_node_versions {
        uuid id PK "uuid"
        uuid node_id FK "uuid, ON DELETE CASCADE"
        int version "integer, UNIQUE node_id mas version, uidx_node_version"
        varchar title "varchar 255"
        text content "text"
        vector embedding "vector 768, opcional. CREATE INDEX ix_versions_embedding USING hnsw con vector_cosine_ops"
        jsonb metadata "jsonb default objeto vacio"
        timestamptz created_at "timestamptz. btree ix_versions_created_at"
        varchar author "varchar 100"
        uuid parent_version_id FK "uuid, FK a la misma tabla, sin cascada"
        float confidence "float8 default 0.5"
        float importance "float8 default 0.5"
        varchar status "varchar 20 default active"
        jsonb evidence "jsonb default lista vacia"
        float salience "float8 default 0.5"
        timestamptz tombstoned_at "timestamptz opcional. índice parcial ix_versions_active en node_id WHERE tombstoned_at IS NULL"
        uuid source_id FK "uuid opcional, FK a sources"
    }
    relations {
        uuid source_id PK, FK "uuid, ON DELETE CASCADE. índice parcial ix_relations_source_active WHERE valid_to IS NULL"
        uuid target_id PK, FK "uuid, ON DELETE CASCADE"
        varchar relation_type PK "varchar 50"
        timestamptz valid_from PK "timestamptz default now"
        timestamptz valid_to "timestamptz opcional"
        jsonb metadata "jsonb default objeto vacio"
    }
    knowledge_event_log {
        uuid event_id PK "uuid"
        varchar event_type "varchar 100"
        jsonb payload "jsonb default objeto vacio"
        timestamptz logged_at "timestamptz default now"
    }
    reasoning_episodes {
        uuid id PK "uuid, el correlation_id de la corrida"
        text goal "text"
        uuid correlation_id "uuid. btree ix_reasoning_episodes_correlation"
        varchar agent "varchar 100"
        varchar status "varchar 20 default running"
        timestamptz started_at "timestamptz default now"
        timestamptz ended_at "timestamptz opcional"
        text final_output "text opcional"
    }
    reasoning_steps {
        uuid id PK "uuid"
        uuid episode_id FK "uuid, ON DELETE CASCADE. btree ix_reasoning_steps_episode"
        int step_index "integer"
        varchar kind "varchar 20"
        text input "text opcional"
        text output "text opcional"
        varchar capability_name "varchar 100 opcional"
        bool approved "boolean opcional"
        text feedback "text opcional"
        timestamptz created_at "timestamptz default now"
        jsonb knowledge_refs "jsonb default lista vacia. CREATE INDEX ix_reasoning_steps_knowledge_refs USING gin con jsonb_path_ops"
    }`,
      basedOn: basedOnSchema,
    },
    {
      id: "2.6",
      slug: "diccionario-de-datos",
      title: "Diagrama de diccionario de datos",
      status: "generated",
      description:
        "Qué significa cada columna de las siete tablas, en el mismo dibujo. Los tipos son los de Postgres. El detalle de cada índice está en el modelo físico.",
      mermaid: `erDiagram
    direction TB
    knowledge_nodes ||--|{ knowledge_node_versions : versiones
    knowledge_node_versions |o--o{ knowledge_node_versions : parent_version_id
    sources |o--o{ knowledge_node_versions : procedencia
    knowledge_nodes ||--o{ relations : origen
    knowledge_nodes ||--o{ relations : destino
    reasoning_episodes ||--o{ reasoning_steps : pasos
    reasoning_steps }o--o{ knowledge_nodes : "cita sin clave"

    knowledge_nodes {
        uuid id PK "Identificador del objeto, uuid7"
        varchar object_type "Tipo, por ejemplo note, decision o evidence"
        timestamptz created_at "Cuándo se creó el objeto"
    }
    sources {
        uuid id PK "Identificador de la fuente"
        varchar kind "Canal, por ejemplo cli, whatsapp, pdf, audio o agent"
        text uri "Dónde estaba el original"
        text raw_ref "Referencia cruda, por ejemplo el id del mensaje"
        timestamptz captured_at "Cuándo se capturó"
        jsonb metadata "Datos extra del canal"
    }
    knowledge_node_versions {
        uuid id PK "Identificador de esta version"
        uuid node_id FK "Objeto al que pertenece"
        int version "Número de versión. Junto con node_id no se repite"
        varchar title "Título visible, hasta 255 caracteres"
        text content "Texto completo de esta versión"
        vector embedding "Vector de 768 números para buscar por significado. Puede faltar"
        jsonb metadata "Datos extra de esta versión"
        timestamptz created_at "Cuándo se escribió esta versión"
        varchar author "Quién la escribió"
        uuid parent_version_id FK "Versión anterior. Vacío en la primera"
        float confidence "Confianza de 0 a 1. Arranca en 0.5"
        float importance "Importancia de 0 a 1. Arranca en 0.5"
        varchar status "Ciclo de vida, por ejemplo active, draft o archived"
        jsonb evidence "Citas que la sostienen, cada una con peso"
        float salience "Qué tan presente está. Arranca en 0.5"
        timestamptz tombstoned_at "Marca de archivo. Vacio si sigue visible"
        uuid source_id FK "Fuente de esta version. Puede faltar"
    }
    relations {
        uuid source_id PK, FK "Objeto de origen"
        uuid target_id PK, FK "Objeto de destino"
        varchar relation_type PK "Tipo, por ejemplo EVIDENCES o RELATED_TO"
        timestamptz valid_from PK "Desde cuándo vale esta relación"
        timestamptz valid_to "Hasta cuándo valió. Vacío si sigue activa"
        jsonb metadata "Datos extra de la relacion"
    }
    knowledge_event_log {
        uuid event_id PK "Identificador del evento"
        varchar event_type "Nombre del hecho, por ejemplo conocimiento creado"
        jsonb payload "Contenido del hecho"
        timestamptz logged_at "Cuándo se anotó, en la misma transacción"
    }
    reasoning_episodes {
        uuid id PK "Identificador del episodio. Coincide con correlation_id"
        text goal "Lo que se le pidió al agente"
        uuid correlation_id "Id de la corrida, para seguirla en los logs"
        varchar agent "Nombre del agente que pensó"
        varchar status "running, completed, failed o pending_approval"
        timestamptz started_at "Cuándo empezó"
        timestamptz ended_at "Cuándo terminó. Vacío si sigue"
        text final_output "Respuesta final. Vacio hasta el cierre"
    }
    reasoning_steps {
        uuid id PK "Identificador del paso"
        uuid episode_id FK "Episodio al que pertenece"
        int step_index "Orden del paso dentro del episodio"
        varchar kind "plan, execute, review, replan o conclude"
        text input "Lo que entro al paso"
        text output "Lo que salio del paso"
        varchar capability_name "Herramienta usada, si el paso ejecutó una"
        bool approved "Si hacía falta aprobación, el resultado. Vacío si no aplica"
        text feedback "Comentario de la revisión"
        timestamptz created_at "Cuándo se anotó el paso"
        jsonb knowledge_refs "Ids de nodos citados o creados. No es una clave foranea"
    }`,
      basedOn: basedOnSchema,
    },
  ],
};
