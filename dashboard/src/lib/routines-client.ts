// Cliente de rutinas del agente. Habla solo con el Gateway, igual que el resto de la Dashboard.
import { ApiError, request } from "./api-client";

export type RoutineStatus = "pending_activation" | "active" | "paused" | "archived";

export interface Routine {
  id: string;
  title: string;
  prompt: string;
  schedule: string;
  schedule_description: string;
  timezone: string;
  status: RoutineStatus;
  created_by: "assistant" | "user";
  created_at: string;
  next_run_at: string | null;
  last_run_at: string | null;
  runs_count: number;
}

export interface RoutineRun {
  id: string;
  routine_id: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "ok" | "error";
  output: string;
}

export interface CreateRoutineInput {
  title: string;
  prompt: string;
  schedule: string;
  timezone?: string | null;
}

export interface RoutineFormErrors {
  title?: string;
  prompt?: string;
  schedule?: string;
  form?: string;
}

type RoutineField = "title" | "prompt" | "schedule";

function routinePath(id: string, suffix = ""): string {
  return `/api/v1/agents/routines/${encodeURIComponent(id)}${suffix}`;
}

export function listRoutines(): Promise<{ routines: Routine[] }> {
  return request("/api/v1/agents/routines");
}

export function createRoutine(input: CreateRoutineInput): Promise<Routine> {
  return request("/api/v1/agents/routines", { method: "POST", body: input });
}

export function activateRoutine(id: string): Promise<Routine> {
  return request(routinePath(id, "/activate"), { method: "POST" });
}

export function pauseRoutine(id: string): Promise<Routine> {
  return request(routinePath(id, "/pause"), { method: "POST" });
}

export function archiveRoutine(id: string): Promise<Routine> {
  return request(routinePath(id, "/archive"), { method: "POST" });
}

/**
 * Pide una ejecución inmediata. El Gateway responde 202, a veces sin cuerpo: `request` intenta
 * leer JSON y, si el cuerpo viene vacío, lanza SyntaxError. Eso no es un fallo de la acción.
 */
export async function runRoutine(id: string): Promise<void> {
  try {
    await request<unknown>(routinePath(id, "/run"), { method: "POST" });
  } catch (err) {
    if (err instanceof SyntaxError) return;
    throw err;
  }
}

export function listRoutineRuns(id: string): Promise<{ runs: RoutineRun[] }> {
  return request(routinePath(id, "/runs"));
}

function detailText(detail: unknown): string {
  if (typeof detail === "string") return detail.trim();
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item.trim();
        if (item && typeof item === "object" && "msg" in item && typeof (item as { msg: unknown }).msg === "string") {
          return (item as { msg: string }).msg.trim();
        }
        return "";
      })
      .filter(Boolean)
      .join(" ");
  }
  if (detail && typeof detail === "object") {
    return Object.values(detail)
      .filter((value): value is string => typeof value === "string" && value.trim().length > 0)
      .join(" ");
  }
  return "";
}

/** Texto legible de un fallo del Gateway, para mostrarlo tal cual en la vista. */
export function routineErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    const text = detailText(err.detail);
    if (text) return text;
  }
  return fallback;
}

function fieldFromLoc(loc: unknown): RoutineField | null {
  if (!Array.isArray(loc)) return null;
  for (let index = loc.length - 1; index >= 0; index -= 1) {
    const part = loc[index];
    if (part === "title" || part === "prompt" || part === "schedule") return part;
  }
  return null;
}

/** Los mensajes por defecto de validación llegan en inglés: la vista habla en español. */
function humanizeFieldMessage(field: RoutineField, message: string): string {
  if (/at least 1 character/i.test(message) || /field required/i.test(message)) {
    if (field === "title") return "Escribe un título.";
    if (field === "prompt") return "Escribe qué debe hacer el agente.";
    return "Escribe una expresión de cinco campos. Por ejemplo, 0 9 * * 1.";
  }
  const max = /at most (\d+) characters/i.exec(message);
  if (max) return `Usa como máximo ${max[1]} caracteres.`;
  return message;
}

function assignStringDetail(detail: string): RoutineFormErrors {
  const named = /^(title|prompt|schedule)\s*:\s*(.+)$/i.exec(detail);
  if (named && (named[1] === "title" || named[1] === "prompt" || named[1] === "schedule")) {
    const field = named[1].toLowerCase() as RoutineField;
    return { [field]: named[2] };
  }
  if (/cron|horario|expresi[oó]n|cinco campos|schedule/i.test(detail)) return { schedule: detail };
  if (/t[ií]tulo|\btitle\b/i.test(detail)) return { title: detail };
  if (/\bprompt\b|qu[eé] debe hacer|instrucci[oó]n/i.test(detail)) return { prompt: detail };
  return { form: detail };
}

/** Reparte un 422 entre los campos del formulario. El resto queda como aviso del formulario. */
export function routineFormErrors(err: unknown): RoutineFormErrors {
  if (!(err instanceof ApiError)) {
    return { form: "No se pudo crear la rutina. Revisa la conexión e inténtalo de nuevo." };
  }
  const detail = err.detail as unknown;
  if (Array.isArray(detail)) {
    const fields: RoutineFormErrors = {};
    for (const item of detail) {
      if (!item || typeof item !== "object") continue;
      const record = item as { loc?: unknown; msg?: unknown };
      const field = fieldFromLoc(record.loc);
      if (!field || typeof record.msg !== "string" || fields[field]) continue;
      fields[field] = humanizeFieldMessage(field, record.msg);
    }
    if (fields.title || fields.prompt || fields.schedule) return fields;
  }
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const record = detail as Record<string, unknown>;
    const fields: RoutineFormErrors = {};
    for (const field of ["title", "prompt", "schedule"] as const) {
      const value = record[field];
      if (typeof value === "string" && value.trim()) fields[field] = value.trim();
    }
    if (fields.title || fields.prompt || fields.schedule) return fields;
  }
  const text = detailText(detail);
  if (err.status === 422 && text) return assignStringDetail(text);
  return { form: text || "No se pudo crear la rutina. Revisa los datos e inténtalo de nuevo." };
}
