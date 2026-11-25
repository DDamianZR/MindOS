# Fase 8 — Agente con poderes, consola con estadísticas y catálogo de diagramas

> **Numeración:** Fase 8; el archivo es `09-` (el `07-` es el runway y el `08-` la Fase 7).
> Tareas `F8-Tn`. Depende de la Fase 7 (asistente sobre Claude).
>
> **Cómo se organizó:** primero la base común (diseño, contratos en `schemas/` y el tipo del
> catálogo de diagramas); después el resto en piezas independientes con archivos disjuntos, cada
> una revisada y verificada antes de integrarla (ver `NOTAS.md`).

## Qué distingue a MindOS de otro asistente con IA

Un asistente con IA típico es una conversación con un historial. MindOS es al revés: **tu
memoria es el producto y el asistente es la forma de hablar con ella.** De ahí salen siete
diferencias concretas, todas ya implementadas:

| # | MindOS | Un asistente típico |
|---|---|---|
| 1 | **Memoria propia y estructurada**: un grafo de objetos cognitivos (notas, decisiones, hipótesis, aprendizajes) con relaciones tipadas, no un historial de mensajes. | Recuerda fragmentos sueltos de chats anteriores, sin estructura. |
| 2 | **Procedencia**: cada dato sabe de dónde vino (WhatsApp, un PDF, una nota de voz, la web, el propio agente). | No sabe de dónde sacó lo que dice. |
| 3 | **Tiempo**: nada se borra; todo se versiona. Puedes preguntar *qué pensabas en marzo* y obtener la versión vigente entonces. | Sobrescribe o pierde lo anterior. |
| 4 | **Razonamiento auditable**: cada conclusión de un agente queda como episodio en el Thinking Graph, y `/explain` reconstruye la cadena hasta las fuentes. | Responde sin dejar rastro verificable. |
| 5 | **Te señala dónde te contradices**: detecta afirmaciones opuestas en tu propia memoria. | Elige una versión en silencio. |
| 6 | **Captura donde ya estás**: WhatsApp, compartir desde el móvil (PWA), CLI, y otros asistentes vía MCP (MindOS es servidor MCP). | Solo dentro de su propia app. |
| 7 | **Agente con límites y tuyo**: actúa por ti (investiga, ejecuta rutinas) pero lo que corre solo nace pendiente de tu visto bueno, no tiene herramientas para borrar, y el sistema es auto-alojado (modo 100 % local con `LLM_PROVIDER=ollama`). | Actúa en una nube ajena con permisos difusos. |

Esa tabla es la base del mensaje de la portada (`/inicio`) y de la ilustración del hero
("memoria versionada", "razonamiento auditable", "agente con aprobación").

## Poderes de agente añadidos

| Poder | Cómo | Control humano |
|---|---|---|
| **Investigar en la web** | Herramientas de servidor de Claude `web_search_20260209` y `web_fetch_20260209` (corren en Anthropic, sin MCP extra). Las páginas aparecen como fuentes "De la web" junto a la respuesta. | El prompt prohíbe presentar algo de la web como un recuerdo; guardar algo de la web pide permiso y lleva la URL. |
| **Rutinas programadas** | Herramienta `create_routine` (cron de 5 campos + zona IANA) y planificador interno en el servicio de agentes; cada ejecución es un turno del asistente con su salida guardada. | Las que propone el asistente nacen `pending_activation` y no corren hasta que la persona las activa en Agentes → Rutinas. Se pausan y archivan; nunca se borran. |
| **Aprobaciones** | Las existentes de la Fase 1/3 (capacidades con `requires_approval`), ahora dentro de la sección Agentes. | Bandeja de aprobaciones. |

### Siguiente paso: conectores MCP externos (no hecho en esta fase)

La API de Claude puede conectarse a servidores MCP remotos (conector MCP, beta
`mcp-client-2025-11-20`) para dar al agente calendario, correo o GitHub. Se buscaron candidatos en
GitHub el 2026-11-24:

- Correo: `jgalea/mailbox-mcp` (MIT, Gmail/IMAP/JMAP, 11★, activo), `orieg/gws-connector` (MIT, Gmail+Calendar+Drive).
- Calendario: `hannasdev/mcp-server-google-calendar` (StreamableHTTP, sin licencia), `zavora-ai/mcp-calendar`.
- También existen los servidores MCP remotos oficiales de Google Workspace.

**Recomendación:** ninguno de los repos comunitarios tiene adopción suficiente (≤ 11★) para darle
acceso a tu correo sin una revisión de seguridad. Preferir los oficiales de Google Workspace y
que toda herramienta que **escribe** (enviar correo, crear evento) pase por la bandeja de
aprobaciones. Tarea F8-T9.

## Interfaz: sistema visual "consola de investigación sobre papel"

Tinta negra sobre blanco, casi sin cromo; tarjetas pastel que **etiquetan** categorías (sky =
memoria, blush = pensamiento, peach = agente, mint = actividad); una sola banda oscura `#010120`
por vista; esquinas de 4 px; ninguna sombra salvo la navegación fija; Inter Tight para texto y
JetBrains Mono para etiquetas, insignias y botones (sustitutos libres de las tipografías de la
referencia). Tokens en `dashboard/src/app/globals.css`, piezas en `dashboard/src/components/ui.tsx`.

## Tareas

- [x] **F8-T0** Limpieza del repo: diagramas de otras ramas rescatados (docs/uml sin commit,
  docs/modelo-dominio), 7 worktrees y 8 ramas ya fusionadas retirados, carpetas vacías y
  `playground/` fuera, roadmap viejo movido a `plan/diagnostico-inicial.md`.
- [x] **F8-T1** Base de diseño, kit de componentes, navegación superior y contratos.
- [x] **F8-T2** `GET /api/v1/memory/stats`.
- [x] **F8-T3** `GET /api/v1/agents/assistant/stats` con tokens, caché y costo.
- [x] **F8-T4** Investigación web en el asistente.
- [x] **F8-T5** Rutinas programadas con activación humana.
- [x] **F8-T6** Portada `/inicio` con estadísticas.
- [x] **F8-T7** Sección `/diagrams`: visor y catálogo de 78 diagramas en 8 familias: 64 generados, 11 existentes, 3 no aplican.
- [x] **F8-T8** Vistas existentes y Asistente con el sistema visual nuevo; vista `/routines`.
- [ ] **F8-T9** Conectores MCP externos (ver arriba). No iniciado.
- [ ] **F8-T10** Verificación en vivo con `ANTHROPIC_API_KEY` (hereda F7-T7). Hecho: chat,
  herramientas de memoria, investigación web y razonamiento contra la API real (ver `NOTAS.md`,
  Fase 9). Falta: una rutina programada ejecutándose contra la API real.
- [x] **F8-T11** Seguridad: solo una persona con sesión resuelve aprobaciones y activa rutinas
  (la API key de servicio recibe 403). Hallazgo del diagrama 7.7.
- [x] **F8-T12** Persistir en Postgres conversaciones, rutinas y estadísticas de uso
  (`AGENTS_STORE=postgres`; detalle en `NOTAS.md`, Fase 9).
- [ ] **F8-T13** Contar en el costo los tokens de turnos fallidos y las ejecuciones de rutinas.
- [ ] **F8-T14** Decidir qué hacer con los streams `mindos.comms.outbound` y `mindos.memory`, que
  se publican y nadie consume (hallazgo del diagrama 3.10).
