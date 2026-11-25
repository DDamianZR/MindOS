"use client";

import Link from "next/link";
import { type ReactNode, useState } from "react";

import { MonoLabel } from "@/components/ui";
import type { AssistantSource } from "@/lib/assistant-client";

export interface ToolRun {
  id: string;
  name: string;
  label: string;
  status: "running" | "ok" | "error";
  summary: string;
  sources: AssistantSource[];
}

// Forma pasada de cada acción, para la bitácora de un turno ya resuelto.
const DONE_LABELS: Record<string, string> = {
  search_memory: "Buscó en tu memoria",
  save_memory: "Guardó en tu memoria",
  list_decisions: "Revisó tus decisiones",
  find_contradictions: "Buscó contradicciones",
  recall_past_thinking: "Reconstruyó lo que pensabas",
  explain_knowledge: "Trazó el razonamiento",
  get_history: "Revisó el historial",
  web_search: "Buscó en la web",
  web_fetch: "Leyó una página",
  create_routine: "Propuso una rutina",
  list_routines: "Revisó tus rutinas",
};

const TYPE_LABELS: Record<string, string> = {
  note: "nota", idea: "idea", document: "documento", conversation: "conversación",
  concept: "concepto", person: "persona", project: "proyecto", task: "tarea",
  resource: "recurso", technology: "tecnología", event: "evento", observation: "observación",
  experience: "experiencia", question: "pregunta", hypothesis: "hipótesis",
  investigation: "investigación", evidence: "evidencia", decision: "decisión",
  outcome: "resultado", learning: "aprendizaje", fact: "hecho", insight: "hallazgo",
};

function isWebSource(source: AssistantSource): boolean {
  if (source.kind === "web") return true;
  if (source.kind === "memory") return false;
  return !source.node_id && Boolean(source.url);
}

function siteName(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function uniqueSources(tools: ToolRun[]): AssistantSource[] {
  const seen = new Map<string, AssistantSource>();
  for (const tool of tools) {
    for (const source of tool.sources) {
      const key = source.node_id ?? source.url ?? source.title;
      if (!seen.has(key)) seen.set(key, source);
    }
  }
  return [...seen.values()];
}

function MemorySource({ source }: { source: AssistantSource }) {
  return (
    <li>
      <Link
        href={`/explain?node_id=${source.node_id}`}
        className="group flex gap-2.5"
      >
        <span aria-hidden="true" className="w-0.5 shrink-0 bg-sky" />
        <span className="min-w-0">
          <span className="block text-caption leading-snug text-obsidian group-hover:underline">{source.title}</span>
          {source.object_type && (
            <span className="text-caption text-muted">{TYPE_LABELS[source.object_type] ?? source.object_type}</span>
          )}
        </span>
      </Link>
    </li>
  );
}

function WebSource({ source }: { source: AssistantSource }) {
  const url = source.url ?? "";
  const body = (
    <>
      <span aria-hidden="true" className="w-0.5 shrink-0 bg-hairline" />
      <span className="min-w-0">
        <span className="block text-caption leading-snug break-words text-obsidian group-hover:underline">
          {source.title}
          {url && <span className="sr-only"> (se abre en otra pestaña)</span>}
        </span>
        {url && <span className="block font-mono text-mono-sm break-all text-muted">{siteName(url)}</span>}
      </span>
    </>
  );
  return (
    <li>
      {url ? (
        <a href={url} target="_blank" rel="noreferrer noopener" className="group flex gap-2.5">
          {body}
        </a>
      ) : (
        <div className="flex gap-2.5">{body}</div>
      )}
    </li>
  );
}

const VISIBLE_SOURCES = 5;

/**
 * Lista con las primeras fuentes visibles y el resto plegado. Una búsqueda web devuelve hasta
 * 10 páginas por consulta: sin tope, el margen era más largo que la respuesta (visto en vivo).
 */
function CappedList({ items }: { items: ReactNode[] }) {
  const [expanded, setExpanded] = useState(false);
  const hidden = items.length - VISIBLE_SOURCES;
  return (
    <>
      <ul className="mt-2 space-y-2.5">{expanded ? items : items.slice(0, VISIBLE_SOURCES)}</ul>
      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          className="mt-2 font-mono text-mono-sm text-slate underline underline-offset-2 hover:text-obsidian"
        >
          {expanded ? "Ver menos" : `Ver ${hidden} más`}
        </button>
      )}
    </>
  );
}

/**
 * Notas al margen de una respuesta: qué consultó el asistente y de dónde salió
 * (tu memoria o una página). En pantallas anchas vive a la derecha; en angostas se pliega debajo.
 */
export function Marginalia({ tools, thinking }: { tools: ToolRun[]; thinking: string }) {
  const sources = uniqueSources(tools);
  const memory = sources.filter((source) => !isWebSource(source) && source.node_id);
  const web = sources.filter(isWebSource);
  const finished = tools.filter((tool) => tool.status !== "running");
  if (finished.length === 0 && !thinking && memory.length === 0 && web.length === 0) return null;

  return (
    <div className="space-y-4 text-caption leading-snug">
      {finished.length > 0 && (
        <ul className="space-y-1 text-muted">
          {finished.map((tool) => (
            <li key={tool.id} className={tool.status === "error" ? "text-danger" : undefined}>
              {DONE_LABELS[tool.name] ?? tool.label}
              {tool.summary && <span className="block text-caption">{tool.summary}</span>}
            </li>
          ))}
        </ul>
      )}

      {memory.length > 0 && (
        <div>
          <MonoLabel>De tu memoria</MonoLabel>
          <CappedList
            items={memory.map((source) => (
              <MemorySource key={source.node_id ?? source.title} source={source} />
            ))}
          />
        </div>
      )}

      {web.length > 0 && (
        <div>
          <MonoLabel>De la web</MonoLabel>
          <CappedList
            items={web.map((source) => (
              <WebSource key={source.url ?? source.title} source={source} />
            ))}
          />
        </div>
      )}

      {thinking && (
        <details className="text-muted">
          <summary className="cursor-pointer select-none hover:text-obsidian">Cómo lo pensó</summary>
          <p className="mt-2 whitespace-pre-wrap text-caption leading-relaxed">{thinking}</p>
        </details>
      )}
    </div>
  );
}
