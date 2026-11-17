# Fase 7 — Asistente personal sobre la API de Claude

> **Numeración:** esta es la **Fase 7**; el archivo es `08-` porque `07-` es el runway de
> ejecución. Las tareas se identifican como `F7-Tn`.
>
> **Objetivo:** que la forma principal de usar MindOS sea conversar con un asistente personal
> que consulta, conecta y amplía la memoria, corriendo sobre **Claude Sonnet 5.5** vía API.
>
> **Depende de:** Fase 1 (Context Builder, ingesta), Fase 2 (Cognitive Query API, `/explain`),
> Fase 3 (Gateway + auth), Fase 4 (Dashboard).

## Cambio de decisión de arquitectura

La decisión original (`README.md §1`) era **LLM = Ollama local** por soberanía. Se cambia a:

| Rol | Antes | Ahora |
|---|---|---|
| Asistente conversacional | no existía | **Claude Sonnet 5.5** (`claude-sonnet-5-5`) |
| Planner / Reviewer (LangGraph) | `qwen3:8b` en Ollama | Claude si hay credencial; Ollama o Mock si no |
| Embeddings | `nomic-embed-text` en Ollama | **sin cambio** (la API de Claude no ofrece embeddings) |
| Contradicciones (Memory Service) | `qwen3:8b` en Ollama | sin cambio por ahora (ver F7-T9) |

**Motivo:** los modelos locales de 8B no sostienen bien el uso de herramientas en varios pasos, y
el servidor de 16 GB no tiene margen para uno mayor junto a Postgres y Redis.

**Costo que se acepta:** lo que el asistente lee de la memoria para responder (los fragmentos
que recupera, el mensaje de la persona y sus propias respuestas) **sale del servidor hacia la
API de Anthropic**. El conocimiento sigue almacenado solo en el servidor; lo que viaja es lo que
entra en cada conversación. Quien quiera volver a un despliegue 100 % local pone
`LLM_PROVIDER=ollama`: el grafo de agentes sigue funcionando y el asistente queda en modo
demostración.

## Reglas que impone el modelo (no son preferencias)

Claude Sonnet 5.5 rechaza con error 400 varias cosas que modelos anteriores aceptaban. El código
ya las respeta; cualquier cambio debe mantenerlas:

1. **Razonamiento adaptativo siempre activo.** No se envían presupuestos (`budget_tokens`) ni
   `thinking: disabled`. La profundidad se controla con `output_config.effort`.
2. **`tool_choice` se queda en `auto`.** Forzar una herramienta (`any` / `tool`) es un 400.
3. **Sin `temperature` / `top_p` / `top_k`**, y sin prefijar la respuesta del asistente.
4. **Historial solo-anexar.** Los bloques de razonamiento de turnos previos se reenvían sin
   tocar, y `system`, `tools` y los mensajes anteriores no pueden cambiar a mitad de una
   conversación. Por eso: la lista de herramientas es fija (no sale del `CapabilityRegistry`), el
   prompt base no contiene nada variable y la fecha se fija una vez al abrir la conversación.
5. **Leer la respuesta por tipo de bloque**, no por posición: puede empezar con `thinking`.
6. **Un turno declinado** (`stop_reason: "refusal"`) llega como HTTP 200; se comprueba antes de
   leer el contenido.

## Tareas

### [x] F7-T1 — Claude como proveedor de razonamiento
- `agents/src/infrastructure/adapters/anthropic_llm.py`: `AnthropicLlm(LlmPort)`. El modo JSON
  se pide por instrucción y `extract_json` limpia lo que el modelo a veces le añade.
- `agents/src/config.py`: `LLM_PROVIDER` (`auto` | `anthropic` | `ollama` | `mock`),
  `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_EFFORT`, `ANTHROPIC_FALLBACKS`.
- `resolve_llm_provider()` en `agents/src/main.py`: con `auto`, Claude en cuanto hay credencial;
  sin ella, el comportamiento previo (Ollama en producción, Mock en desarrollo).
- **DoD:** `pytest agents/tests/test_anthropic_llm.py` verde; el Planner corre sobre Claude sin cambios.

### [x] F7-T2 — Herramientas del asistente sobre la memoria
- Puerto `MemoryGatewayPort` + adaptador `HttpMemoryGateway`.
- `agents/src/application/assistant/toolbox.py`: siete herramientas (`search_memory`,
  `save_memory`, `list_decisions`, `find_contradictions`, `recall_past_thinking`,
  `explain_knowledge`, `get_history`). Validan la entrada con Pydantic antes de ejecutar y nunca
  lanzan: un fallo vuelve al modelo como resultado de error.
- No hay herramientas de borrado ni archivado (principio #6: nunca borrado duro).
- **DoD:** `pytest agents/tests/test_assistant_toolbox.py` verde, incluido el test que ejercita
  las siete contra el Memory Service real en memoria.

### [x] F7-T3 — Asistente conversacional
- Puerto `PersonalAgentPort` (eventos de un turno) y `ConversationStorePort`.
- `ClaudePersonalAgent`: bucle manual de herramientas con streaming, caché de prompt, llamadas
  en paralelo respondidas en un solo mensaje, y **rollback del turno** ante error, rechazo,
  corte por tokens o desconexión del cliente (el historial nunca queda a medias).
- `DemoPersonalAgent`: sin credencial, busca de verdad en la memoria y responde con un texto
  fijo que dice que es una demostración. Permite probar todo el camino sin API key.
- `InMemoryConversationStore`: conversaciones en memoria del proceso (ver F7-T8).
- **DoD:** `pytest agents/tests/test_claude_personal_agent.py` verde, incluido el test que usa el
  SDK real contra un transporte simulado (serialización de la petición + parseo del stream).

### [x] F7-T4 — Endpoint de chat en streaming
- `agents/src/api/assistant_router.py`: `POST /api/v1/agents/assistant/chat` (SSE),
  `GET .../status`, `GET .../conversations/{id}`. DTOs en `schemas/.../assistant_dto.py`.
- **DoD:** `pytest agents/tests/test_assistant_router.py` verde.

### [x] F7-T5 — Streaming a través del Gateway
- `gateway/src/main.py`: si la petición trae `Accept: text/event-stream`, el proxy reenvía el
  cuerpo evento a evento (`_proxy_stream`) en vez de bufferizarlo. Misma auth y rate-limit.
- **DoD:** `pytest gateway/tests/test_gateway_streaming.py` verde.

### [x] F7-T6 — Vista Asistente y sistema visual del Dashboard
- `/assistant` es la vista inicial: respuesta en streaming, citas «…» resaltadas y enlazadas a
  `/explain`, fuentes consultadas como notas al margen, detener, reintentar, restaurar al recargar.
- Sistema visual en `globals.css` (tokens `paper`/`ink`/`accent`/`mark`, tipografías Archivo y
  Piazzolla, escala `zinc` redefinida para que las vistas previas hereden la paleta).
- Barra lateral agrupada por intención, con menú para móvil. Login rediseñado.
- **DoD:** `npx tsc --noEmit`, `npx eslint src` y `npm run build` limpios; verificado en el
  navegador contra el stack local (`python scripts/dev_stack.py`), en claro, oscuro y móvil.

### [ ] F7-T7 — Verificación en vivo con una API key real
Todo lo anterior se verificó con dobles de prueba y con el modo demostración; **ninguna petición
real a la API de Claude se ha hecho todavía** (no había credencial en el entorno de desarrollo).
- Poner `ANTHROPIC_API_KEY` en `.env`, levantar el stack local y conversar.
- Comprobar: uso de herramientas en varios pasos, citas, guardado de una nota, y que
  `usage.cache_read_input_tokens` sea mayor que cero desde el segundo mensaje.
- Ajustar `ASSISTANT_EFFORT` (`low` → `medium`) si las respuestas se quedan cortas de análisis.
- **DoD:** una conversación real de varios turnos sin errores; anotar en `NOTAS.md` lo que cambie.

### [ ] F7-T8 — Persistir las conversaciones
Hoy se pierden al reiniciar el servicio de agentes. Requiere serializar los bloques del
proveedor (incluidas las firmas de razonamiento) sin alterarlos y una migración Alembic.

### [ ] F7-T9 — Memory Service sobre Claude
La detección de contradicciones (F2-T5) sigue en Ollama. Llevar `AnthropicLlm` a `memory/` (o a
`common/`) y añadir `LLM_PROVIDER=anthropic` allí. Con eso el servidor ya no necesita cargar
ningún modelo de razonamiento local.

### [ ] F7-T10 — El asistente en los demás canales
Las preguntas que llegan por WhatsApp/CLI siguen yendo a `/agents/execute` (grafo
Planner/Executor/Reviewer). Decidir si pasan al asistente conversacional, con una conversación
por remitente.

### [ ] F7-T11 — Trazas del asistente en el Thinking Graph
Registrar cada turno como episodio (qué consultó, qué concluyó) para que `/explain` pueda
mostrar también el razonamiento de una conversación, como ya hace con el grafo de agentes.

### [ ] F7-T12 — Rediseño de las ocho vistas restantes
Heredan paleta y tipografía, pero su maquetación es la de la Fase 4. Rediseñarlas una a una.

## Cómo correrlo en local

```
python scripts/dev_stack.py          # memory + agents + gateway, todo en memoria
python scripts/dev_stack.py seed     # notas de ejemplo
npm --prefix dashboard run dev       # http://localhost:3000
```

Las credenciales de desarrollo las imprime `dev_stack.py` al arrancar.
