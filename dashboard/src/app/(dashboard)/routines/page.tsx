"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";

import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorNotice,
  PageHeader,
  SectionTitle,
  Skeleton,
  formatNumber,
} from "@/components/ui";
import {
  type Routine,
  type RoutineRun,
  activateRoutine,
  archiveRoutine,
  createRoutine,
  listRoutineRuns,
  listRoutines,
  pauseRoutine,
  routineErrorMessage,
  routineFormErrors,
  runRoutine,
} from "@/lib/routines-client";

const PRESETS = [
  { id: "daily", label: "Cada día a las 9:00", cron: "0 9 * * *" },
  { id: "monday", label: "Cada lunes a las 9:00", cron: "0 9 * * 1" },
  { id: "sunday", label: "Cada domingo a las 20:00", cron: "0 20 * * 0" },
  { id: "month", label: "El día 1 de cada mes a las 9:00", cron: "0 9 1 * *" },
  { id: "custom", label: "Personalizado", cron: "" },
] as const;

type PresetId = (typeof PRESETS)[number]["id"];
type BusyAction = "activate" | "pause" | "archive" | "run";

const FIELD =
  "w-full min-h-12 rounded-md border border-hairline bg-paper px-3 py-3 text-body-sm text-obsidian placeholder:text-muted";

function browserTimeZone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return undefined;
  }
}

function zoneOrLocal(timeZone: string): string | undefined {
  try {
    new Intl.DateTimeFormat("es", { timeZone }).format(0);
    return timeZone;
  } catch {
    return undefined;
  }
}

/**
 * Día civil en la zona de la rutina. Restar milisegundos movería "mañana" cuando cambia la hora.
 */
function calendarDay(date: Date, timeZone: string | undefined): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function formatWhen(iso: string, timeZone: string): { relative: string; absolute: string } | null {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  const zone = zoneOrLocal(timeZone);
  const clock: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit", hourCycle: "h23" };
  const absolute = new Intl.DateTimeFormat("es", {
    timeZone: zone,
    day: "numeric",
    month: "long",
    year: "numeric",
    ...clock,
  }).format(date);
  const time = new Intl.DateTimeFormat("es", { timeZone: zone, ...clock }).format(date);
  const dayDiff = Math.round(
    (Date.parse(`${calendarDay(date, zone)}T00:00:00Z`) - Date.parse(`${calendarDay(new Date(), zone)}T00:00:00Z`)) /
      86_400_000,
  );
  const relativeDay = new Intl.RelativeTimeFormat("es", { numeric: "auto" });
  let relative: string;
  if (Math.abs(dayDiff) <= 2) {
    relative = `${relativeDay.format(dayDiff, "day")} a las ${time}`;
  } else if (Math.abs(dayDiff) < 7) {
    const weekday = new Intl.DateTimeFormat("es", { timeZone: zone, weekday: "long" }).format(date);
    relative = `el ${weekday} a las ${time}`;
  } else {
    relative = relativeDay.format(dayDiff, "day");
  }
  return { relative, absolute };
}

function WhenLine({ label, iso, timeZone, empty }: { label: string; iso: string | null; timeZone: string; empty: string }) {
  const when = iso ? formatWhen(iso, timeZone) : null;
  return (
    <div>
      <p className="font-mono text-mono-sm text-muted">{label}</p>
      {when ? (
        <>
          <p className="mt-1 text-body-sm text-obsidian">{when.relative}</p>
          <p className="font-mono text-mono-sm text-muted">{when.absolute}</p>
        </>
      ) : (
        <p className="mt-1 text-body-sm text-slate">{empty}</p>
      )}
    </div>
  );
}

function runsLabel(count: number): string {
  return count === 1 ? "1 ejecución" : `${formatNumber(count)} ejecuciones`;
}

function replaceRoutine(list: Routine[], next: Routine): Routine[] {
  if (next.status === "archived") return list.filter((item) => item.id !== next.id);
  const exists = list.some((item) => item.id === next.id);
  if (!exists) return [next, ...list];
  return list.map((item) => (item.id === next.id ? next : item));
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <div id={id} className="mt-2">
      <ErrorNotice>{message}</ErrorNotice>
    </div>
  );
}

function RunOutput({ output }: { output: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = output.split("\n").length > 12 || output.length > 320;
  if (!output.trim()) {
    return <p className="text-body-sm text-slate">Esta ejecución no dejó texto.</p>;
  }
  return (
    <div>
      <p className={`whitespace-pre-wrap text-body-sm text-obsidian ${!expanded && long ? "line-clamp-12" : ""}`}>
        {output}
      </p>
      {long && (
        <Button
          type="button"
          variant="ghost"
          className="mt-3"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Ver menos" : "Ver todo"}
        </Button>
      )}
    </div>
  );
}

const RUN_STATUS: Record<RoutineRun["status"], string> = {
  running: "En curso",
  ok: "Completada",
  error: "Con un problema",
};

function RoutineRuns({ routineId, timeZone, refreshKey }: { routineId: string; timeZone: string; refreshKey: number }) {
  const [runs, setRuns] = useState<RoutineRun[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const openRef = useRef(false);
  const ticket = useRef(0);

  const load = useCallback(async () => {
    const current = ++ticket.current;
    setLoading(true);
    setError(null);
    try {
      const data = await listRoutineRuns(routineId);
      if (current !== ticket.current) return;
      setRuns(data.runs);
    } catch (err) {
      if (current !== ticket.current) return;
      setError(routineErrorMessage(err, "No se pudieron cargar las ejecuciones. Ábrelas de nuevo en un momento."));
    } finally {
      if (current === ticket.current) setLoading(false);
    }
  }, [routineId]);

  useEffect(() => {
    // El panel ya está abierto: hay que volver a pedir las ejecuciones tras "Ejecutar ahora".
    if (!openRef.current || refreshKey === 0) return;
    void load();
  }, [refreshKey, load]);

  return (
    <details
      className="mt-4 border-t border-hairline pt-3"
      onToggle={(event) => {
        const open = event.currentTarget.open;
        openRef.current = open;
        if (open) void load();
      }}
    >
      <summary className="cursor-pointer font-mono text-mono text-slate">Ver ejecuciones</summary>
      <div className="mt-3 space-y-4">
        {loading && (
          <>
            <p role="status" className="sr-only">
              Cargando ejecuciones.
            </p>
            <Skeleton className="h-16 w-full" />
          </>
        )}
        {error && <ErrorNotice>{error}</ErrorNotice>}
        {runs && runs.length === 0 && !loading && (
          <p className="text-body-sm text-slate">Todavía no hay ejecuciones.</p>
        )}
        {runs && runs.length > 0 && (
          <ul className="space-y-4">
            {runs.map((run) => {
              const when = formatWhen(run.started_at, timeZone);
              return (
                <li key={run.id} className="border-t border-hairline pt-3 first:border-t-0 first:pt-0">
                  <p className="text-body-sm text-obsidian">{when ? when.relative : "Fecha no disponible"}</p>
                  {when && <p className="font-mono text-mono-sm text-muted">{when.absolute}</p>}
                  <p className="mt-1 font-mono text-mono-sm text-slate">{RUN_STATUS[run.status]}</p>
                  <div className="mt-2">
                    <RunOutput output={run.output} />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </details>
  );
}

function RoutineActions({
  routine,
  busy,
  confirming,
  onActivate,
  onPause,
  onAskArchive,
  onConfirmArchive,
  onCancelArchive,
  onRun,
}: {
  routine: Routine;
  busy: BusyAction | null;
  confirming: boolean;
  onActivate: () => void;
  onPause: () => void;
  onAskArchive: () => void;
  onConfirmArchive: () => void;
  onCancelArchive: () => void;
  onRun: () => void;
}) {
  const disabled = busy !== null;
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      <Button type="button" variant="ghost" disabled={disabled} onClick={onRun}>
        {busy === "run" ? "Ejecutando…" : "Ejecutar ahora"}
      </Button>
      {routine.status === "active" ? (
        <Button type="button" variant="ghost" disabled={disabled} onClick={onPause}>
          {busy === "pause" ? "Pausando…" : "Pausar"}
        </Button>
      ) : (
        <Button type="button" disabled={disabled} onClick={onActivate}>
          {busy === "activate" ? "Activando…" : "Activar"}
        </Button>
      )}
      {confirming ? (
        <div className="basis-full rounded-md border border-hairline p-3">
          <p className="text-body-sm text-obsidian">
            ¿Archivar esta rutina? Dejará de correr y no aparecerá en la lista.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" disabled={disabled} onClick={onConfirmArchive}>
              {busy === "archive" ? "Archivando…" : "Archivar"}
            </Button>
            <Button type="button" variant="ghost" disabled={disabled} onClick={onCancelArchive}>
              Cancelar
            </Button>
          </div>
        </div>
      ) : (
        <Button type="button" variant="ghost" disabled={disabled} onClick={onAskArchive}>
          Archivar
        </Button>
      )}
    </div>
  );
}

function NewRoutineForm({ onCreated }: { onCreated: (routine: Routine) => void }) {
  const baseId = useId();
  const titleRef = useRef<HTMLInputElement>(null);
  const promptRef = useRef<HTMLTextAreaElement>(null);
  const firstWhenRef = useRef<HTMLInputElement>(null);
  const scheduleRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [preset, setPreset] = useState<PresetId | "">("");
  const [cron, setCron] = useState("");
  const [errors, setErrors] = useState<ReturnType<typeof routineFormErrors>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    titleRef.current?.focus();
  }, []);

  const titleErrorId = `${baseId}-title-error`;
  const promptErrorId = `${baseId}-prompt-error`;
  const scheduleErrorId = `${baseId}-schedule-error`;
  const cronHelpId = `${baseId}-cron-help`;

  function localErrors(): ReturnType<typeof routineFormErrors> {
    const next: ReturnType<typeof routineFormErrors> = {};
    const cleanTitle = title.trim();
    const cleanPrompt = prompt.trim();
    if (!cleanTitle) next.title = "Escribe un título.";
    else if (cleanTitle.length > 120) next.title = "El título admite hasta 120 caracteres.";
    if (!cleanPrompt) next.prompt = "Escribe qué debe hacer el agente.";
    else if (cleanPrompt.length > 4000) next.prompt = "Ese texto admite hasta 4000 caracteres.";
    if (!preset) next.schedule = "Elige cuándo debe correr.";
    else if (preset === "custom") {
      const expression = cron.trim();
      if (!expression) next.schedule = "Escribe la expresión cron.";
      else if (expression.split(/\s+/).length !== 5) {
        next.schedule = "Hacen falta cinco campos separados por espacios. Por ejemplo, 30 18 * * 5.";
      }
    }
    return next;
  }

  function focusFirst(next: ReturnType<typeof routineFormErrors>) {
    if (next.title) titleRef.current?.focus();
    else if (next.prompt) promptRef.current?.focus();
    else if (next.schedule && preset === "custom") scheduleRef.current?.focus();
    else if (next.schedule) firstWhenRef.current?.focus();
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = localErrors();
    if (next.title || next.prompt || next.schedule) {
      setErrors(next);
      focusFirst(next);
      return;
    }
    const chosen = PRESETS.find((item) => item.id === preset);
    const schedule = preset === "custom" ? cron.trim() : chosen?.cron ?? "";
    setSubmitting(true);
    setErrors({});
    try {
      const created = await createRoutine({
        title: title.trim(),
        prompt: prompt.trim(),
        schedule,
        timezone: browserTimeZone() ?? null,
      });
      onCreated(created);
    } catch (err) {
      const parsed = routineFormErrors(err);
      setErrors(parsed);
      focusFirst(parsed);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <div id={`${baseId}-heading`}>
        <SectionTitle>Nueva rutina</SectionTitle>
      </div>
      <form noValidate aria-labelledby={`${baseId}-heading`} onSubmit={handleSubmit} className="max-w-[40rem]">
        {errors.form && (
          <div className="mb-4">
            <ErrorNotice>{errors.form}</ErrorNotice>
          </div>
        )}
        <div className="mb-4">
          <label htmlFor={`${baseId}-title`} className="mb-1 block text-caption font-medium text-obsidian">
            Título
          </label>
          <input
            ref={titleRef}
            id={`${baseId}-title`}
            name="title"
            value={title}
            required
            maxLength={120}
            aria-required="true"
            aria-invalid={errors.title ? true : undefined}
            aria-describedby={errors.title ? titleErrorId : undefined}
            onChange={(event) => {
              const value = event.target.value;
              setTitle(value);
              setErrors((current) => (current.title ? { ...current, title: value.trim() ? undefined : current.title } : current));
            }}
            className={FIELD}
          />
          <FieldError id={titleErrorId} message={errors.title} />
        </div>
        <div className="mb-4">
          <label htmlFor={`${baseId}-prompt`} className="mb-1 block text-caption font-medium text-obsidian">
            Qué debe hacer
          </label>
          <textarea
            ref={promptRef}
            id={`${baseId}-prompt`}
            name="prompt"
            value={prompt}
            required
            maxLength={4000}
            rows={4}
            aria-required="true"
            aria-invalid={errors.prompt ? true : undefined}
            aria-describedby={errors.prompt ? promptErrorId : undefined}
            onChange={(event) => {
              const value = event.target.value;
              setPrompt(value);
              setErrors((current) =>
                current.prompt ? { ...current, prompt: value.trim() ? undefined : current.prompt } : current,
              );
            }}
            className={`${FIELD} min-h-28 resize-y`}
          />
          <FieldError id={promptErrorId} message={errors.prompt} />
        </div>
        <fieldset
          className="mb-5"
          aria-invalid={errors.schedule && preset !== "custom" ? true : undefined}
          aria-describedby={errors.schedule && preset !== "custom" ? scheduleErrorId : undefined}
        >
          <legend className="mb-2 text-caption font-medium text-obsidian">Cuándo</legend>
          <div className="space-y-1">
            {PRESETS.map((item, index) => (
              <label key={item.id} className="flex min-h-12 items-center gap-3 text-body-sm text-obsidian">
                <input
                  ref={index === 0 ? firstWhenRef : undefined}
                  type="radio"
                  name={`${baseId}-when`}
                  value={item.id}
                  checked={preset === item.id}
                  onChange={() => {
                    setPreset(item.id);
                    setErrors((current) => ({ ...current, schedule: undefined }));
                  }}
                  className="size-4 accent-obsidian"
                />
                {item.label}
              </label>
            ))}
          </div>
          {preset === "custom" && (
            <div className="mt-3">
              <label htmlFor={`${baseId}-schedule`} className="mb-1 block text-caption font-medium text-obsidian">
                Expresión cron
              </label>
              <input
                ref={scheduleRef}
                id={`${baseId}-schedule`}
                name="schedule"
                value={cron}
                required
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="none"
                spellCheck={false}
                aria-invalid={errors.schedule ? true : undefined}
                aria-describedby={errors.schedule ? `${cronHelpId} ${scheduleErrorId}` : cronHelpId}
                onChange={(event) => {
                  const value = event.target.value;
                  setCron(value);
                  setErrors((current) => {
                    if (!current.schedule) return current;
                    const fields = value.trim().split(/\s+/).filter(Boolean);
                    return fields.length === 5 ? { ...current, schedule: undefined } : current;
                  });
                }}
                className={`${FIELD} font-mono`}
              />
              <FieldError id={scheduleErrorId} message={errors.schedule} />
              <p id={cronHelpId} className="mt-2 text-caption text-slate">
                Cinco campos separados por espacios: minuto, hora, día del mes, mes y día de la semana. Por ejemplo, 30
                18 * * 5.
              </p>
            </div>
          )}
          {preset !== "custom" && <FieldError id={scheduleErrorId} message={errors.schedule} />}
        </fieldset>
        <Button type="submit" disabled={submitting} aria-busy={submitting}>
          {submitting ? "Creando…" : "Crear rutina"}
        </Button>
      </form>
    </Card>
  );
}

export default function RoutinesPage() {
  const [routines, setRoutines] = useState<Routine[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState<{ id: string; action: BusyAction } | null>(null);
  const [cardErrors, setCardErrors] = useState<Record<string, string>>({});
  const [notices, setNotices] = useState<Record<string, string>>({});
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [refreshKeys, setRefreshKeys] = useState<Record<string, number>>({});
  const statusRef = useRef<HTMLParagraphElement>(null);

  function load() {
    setLoading(true);
    setLoadError(null);
    listRoutines()
      .then((data) => setRoutines(data.routines.filter((routine) => routine.status !== "archived")))
      .catch((err) =>
        setLoadError(routineErrorMessage(err, "No se pudieron cargar las rutinas. Revisa la conexión e inténtalo de nuevo.")),
      )
      .finally(() => setLoading(false));
  }

  // Al entrar se pide la lista. El estado de carga ya está puesto, antes de que responda el Gateway.
  useEffect(load, []);

  function announce(message: string, moveFocus = false) {
    setStatus(message);
    if (moveFocus) requestAnimationFrame(() => statusRef.current?.focus());
  }

  async function mutate(id: string, action: BusyAction, run: () => Promise<Routine>, success: string) {
    setBusy({ id, action });
    setCardErrors((current) => ({ ...current, [id]: "" }));
    try {
      const next = await run();
      setRoutines((current) => (current ? replaceRoutine(current, next) : [next]));
      if (action === "archive") setConfirmId(null);
      announce(success, action === "archive");
    } catch (err) {
      setCardErrors((current) => ({
        ...current,
        [id]: routineErrorMessage(err, "No se pudo completar la acción. Inténtalo de nuevo."),
      }));
    } finally {
      setBusy(null);
    }
  }

  async function handleRun(id: string) {
    setBusy({ id, action: "run" });
    setCardErrors((current) => ({ ...current, [id]: "" }));
    try {
      await runRoutine(id);
      setNotices((current) => ({
        ...current,
        [id]: "Se pidió ejecutarla ahora. El resultado aparecerá en las ejecuciones.",
      }));
      setRefreshKeys((current) => ({ ...current, [id]: (current[id] ?? 0) + 1 }));
      announce("Se pidió ejecutar la rutina.");
    } catch (err) {
      setCardErrors((current) => ({
        ...current,
        [id]: routineErrorMessage(err, "No se pudo ejecutar la rutina. Inténtalo de nuevo."),
      }));
    } finally {
      setBusy(null);
    }
  }

  const visible = routines ?? [];
  const pending = visible.filter((routine) => routine.status === "pending_activation");
  const own = visible.filter((routine) => routine.status !== "pending_activation");
  const isEmpty = routines !== null && visible.length === 0;

  return (
    <>
      <PageHeader
        title="Rutinas"
        continuation="lo que el agente hace por ti cada cierto tiempo"
        description="Tareas que el agente ejecuta solo, a la hora que indiques. Las que propone el asistente no corren hasta que las actives."
        actions={
          visible.length > 0 ? (
            <Button
              type="button"
              variant="ghost"
              aria-expanded={formOpen}
              aria-controls="nueva-rutina"
              onClick={() => setFormOpen((open) => !open)}
            >
              Nueva rutina
            </Button>
          ) : undefined
        }
      />

      <p ref={statusRef} tabIndex={-1} role="status" className={status ? "mb-8 text-body-sm text-obsidian" : "sr-only"}>
        {status}
      </p>

      {loading && (
        <div className="space-y-3">
          <p role="status" className="sr-only">
            Cargando rutinas.
          </p>
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      )}

      {loadError && (
        <div className="space-y-3">
          <ErrorNotice>{loadError}</ErrorNotice>
          <Button type="button" variant="ghost" onClick={load}>
            Reintentar
          </Button>
        </div>
      )}

      {isEmpty && (
        <EmptyState
          title="Todavía no hay rutinas."
          action={
            <Button type="button" onClick={() => setFormOpen(true)}>
              Nueva rutina
            </Button>
          }
        >
          Pídele al asistente algo como «cada lunes a las 9 resúmeme las decisiones pendientes», o crea una aquí.
        </EmptyState>
      )}

      {formOpen && (
        <div id="nueva-rutina" className={isEmpty ? "mt-8" : undefined}>
          <NewRoutineForm
            onCreated={(routine) => {
              setRoutines((current) => replaceRoutine(current ?? [], routine));
              setFormOpen(false);
              announce("Rutina creada");
            }}
          />
        </div>
      )}

      {pending.length > 0 && (
        <section className="mt-12" aria-labelledby="rutinas-propuestas">
          <div id="rutinas-propuestas">
            <SectionTitle>Esperan tu visto bueno</SectionTitle>
          </div>
          <ul className="space-y-4">
            {pending.map((routine) => {
              const cardBusy = busy?.id === routine.id ? busy.action : null;
              return (
                <Card key={routine.id} as="li" className="relative overflow-hidden">
                  <span aria-hidden="true" className="absolute inset-y-0 left-0 w-0.5 bg-peach" />
                  <h3 className="text-subheading font-medium text-obsidian">{routine.title}</h3>
                  <div className="mt-3">
                    <Badge tone="agente">Propuesta por el asistente</Badge>
                  </div>
                  <p className="mt-3 whitespace-pre-wrap text-body-sm break-words text-obsidian">{routine.prompt}</p>
                  <p className="mt-3 text-body-sm text-slate">{routine.schedule_description}</p>
                  <p className="font-mono text-mono-sm text-muted">{routine.timezone}</p>
                  {cardErrors[routine.id] && (
                    <div className="mt-3">
                      <ErrorNotice>{cardErrors[routine.id]}</ErrorNotice>
                    </div>
                  )}
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      disabled={cardBusy !== null}
                      onClick={() => mutate(routine.id, "activate", () => activateRoutine(routine.id), "Rutina activada.")}
                    >
                      {cardBusy === "activate" ? "Activando…" : "Activar"}
                    </Button>
                    {confirmId === routine.id ? (
                      <div className="basis-full rounded-md border border-hairline p-3">
                        <p className="text-body-sm text-obsidian">
                          ¿Archivar esta rutina? Dejará de correr y no aparecerá en la lista.
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button
                            type="button"
                            disabled={cardBusy !== null}
                            onClick={() => mutate(routine.id, "archive", () => archiveRoutine(routine.id), "Rutina archivada.")}
                          >
                            {cardBusy === "archive" ? "Archivando…" : "Archivar"}
                          </Button>
                          <Button type="button" variant="ghost" disabled={cardBusy !== null} onClick={() => setConfirmId(null)}>
                            Cancelar
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button type="button" variant="ghost" disabled={cardBusy !== null} onClick={() => setConfirmId(routine.id)}>
                        Archivar
                      </Button>
                    )}
                  </div>
                </Card>
              );
            })}
          </ul>
        </section>
      )}

      {own.length > 0 && (
        <section className="mt-16" aria-labelledby="tus-rutinas">
          <div id="tus-rutinas">
            <SectionTitle>Tus rutinas</SectionTitle>
          </div>
          <ul className="space-y-4">
            {own.map((routine) => {
              const cardBusy = busy?.id === routine.id ? busy.action : null;
              return (
                <Card key={routine.id} as="li">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-subheading font-medium text-obsidian">{routine.title}</h3>
                    {routine.status === "active" ? (
                      <Badge tone="actividad">Activa</Badge>
                    ) : (
                      <Badge>En pausa</Badge>
                    )}
                  </div>
                  <p className="mt-3 text-body-sm text-slate">{routine.schedule_description}</p>
                  <p className="font-mono text-mono-sm text-muted">{routine.timezone}</p>
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    <WhenLine
                      label="Próxima ejecución"
                      iso={routine.next_run_at}
                      timeZone={routine.timezone}
                      empty="Sin próxima ejecución"
                    />
                    <WhenLine
                      label="Última ejecución"
                      iso={routine.last_run_at}
                      timeZone={routine.timezone}
                      empty="Todavía no se ha ejecutado"
                    />
                  </div>
                  <p className="mt-4 font-mono text-mono-sm text-muted">{runsLabel(routine.runs_count)}</p>
                  {notices[routine.id] && (
                    <p role="status" className="mt-3 text-caption text-slate">
                      {notices[routine.id]}
                    </p>
                  )}
                  {cardErrors[routine.id] && (
                    <div className="mt-3">
                      <ErrorNotice>{cardErrors[routine.id]}</ErrorNotice>
                    </div>
                  )}
                  <RoutineActions
                    routine={routine}
                    busy={cardBusy}
                    confirming={confirmId === routine.id}
                    onRun={() => void handleRun(routine.id)}
                    onActivate={() => mutate(routine.id, "activate", () => activateRoutine(routine.id), "Rutina activada.")}
                    onPause={() => mutate(routine.id, "pause", () => pauseRoutine(routine.id), "Rutina en pausa.")}
                    onAskArchive={() => setConfirmId(routine.id)}
                    onCancelArchive={() => setConfirmId(null)}
                    onConfirmArchive={() =>
                      mutate(routine.id, "archive", () => archiveRoutine(routine.id), "Rutina archivada.")
                    }
                  />
                  <RoutineRuns routineId={routine.id} timeZone={routine.timezone} refreshKey={refreshKeys[routine.id] ?? 0} />
                </Card>
              );
            })}
          </ul>
        </section>
      )}
    </>
  );
}
