# Fase 5 — Automatización y evolución

**Objetivo:** que el sistema **evolucione con el usuario**: consolide memoria, refloje ideas
dormidas, investigue por su cuenta y modele el ciclo de vida del conocimiento.

**Precondición:** Fase 2 (Thinking Graph). **Nivel:** épica + tareas clave + DoD.

---

## F5-T1 · Agente de reflexión / consolidación (el "sueño")

Job programado (cron interno / Celery-beat / APScheduler) que corre en horas de baja carga y:
- **Resume** clusters de nodos relacionados en `insight`/`summary` de mayor nivel (jerarquía).
- **Enlaza** nodos que deberían estar conectados y no lo están (link prediction por similitud+LLM).
- **Deduplica** y fusiona (respetando versionado; nada se pierde).
- **Ajusta salience**: refuerza lo revisitado/citado, decae lo ignorado (importancia dinámica).
- **Detecta patrones** (temas recurrentes, sesgos, ciclos de decisión) → alimenta `/cognitive/patterns`.
- Emite `com.mindos.memory.consolidation.completed` con un resumen para el digest.

**DoD:** tras una corrida sobre un dataset, se crean `insight` nuevos, enlaces nuevos y cambia la
`salience`; queda un reporte consultable.

## F5-T2 · Resurfacing / digest (repetición espaciada)

- Selecciona conocimiento **dormido pero relevante** (alta importancia, baja actividad reciente, o
  recién conectado a algo actual) y lo **refloja** en un digest (diario/semanal) por el canal del
  usuario (WhatsApp/Dashboard/email).
- Encarna "una idea aparentemente mala puede volverse clave años después".
- **DoD:** el usuario recibe un digest con 3-5 piezas reflotadas relevantes y sus porqués.

## F5-T3 · Agente de investigación

- Dado un tema/pregunta, el agente (Planner→Executor→Reviewer) hace investigación multi-paso
  (busca en memoria, opcionalmente en web si se habilita, sintetiza), y **escribe los hallazgos en el
  Thinking Graph** (Pregunta→Investigación→Evidencias→Insight) con citas.
- Usa `qwen3-coder:30b` en la workstation para síntesis pesada; `qwen3:8b` para pasos ligeros.
- **DoD:** lanzar "investiga X" produce un episodio de razonamiento con evidencias citadas y uno o
  más `insight` persistidos y explicables vía `/explain`.

## F5-T4 · Lifecycle del conocimiento

- Máquina de estados sobre `status`: `hypothesis`→`fact` (cuando la evidencia supera umbral),
  `idea`→`project` (al crear tareas), `project`→`archived`/`learning` (al cerrarse), con eventos por
  transición. Reglas + confirmación del usuario para transiciones sensibles.
- **DoD:** una hipótesis con evidencia suficiente puede promoverse a `fact` (con registro de la
  transición y su justificación); un proyecto cerrado genera un `learning`.

## F5-T5 · Programación y orquestación de jobs

- Elige e integra un scheduler (APScheduler embebido para simplicidad, o un worker Celery + beat si
  crece). Registra: consolidación (nocturna), resurfacing (diario), detección de contradicciones
  (tras ingestas o batch), backups (Fase 6).
- **DoD:** los jobs corren en su horario, son idempotentes y observables (logs+métricas).

## F5-T6 · Harness de evaluación de razonamiento

- Set de casos dorados (pregunta → respuesta/citación esperada) y un evaluador (LLM-as-judge +
  chequeos deterministas) que puntúa calidad de recuperación y explicabilidad. Corre en CI (nightly).
- **DoD:** `make eval` produce un reporte de métricas de calidad reproducible.

---

## Cierre de Fase 5
- [ ] F5-T1 consolidación · [ ] F5-T2 resurfacing · [ ] F5-T3 investigación
- [ ] F5-T4 lifecycle · [ ] F5-T5 scheduler · [ ] F5-T6 eval

**Hito:** MindOS deja de ser reactivo y empieza a **trabajar por su cuenta** para el usuario.
