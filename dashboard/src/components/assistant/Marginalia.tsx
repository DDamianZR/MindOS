"use client";

import Link from "next/link";

import type { AssistantSource } from "@/lib/assistant-client";
import { objectTypeColor } from "@/lib/object-type-style";

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
};

const TYPE_LABELS: Record<string, string> = {
  note: "nota", idea: "idea", document: "documento", conversation: "conversación",
  concept: "concepto", person: "persona", project: "proyecto", task: "tarea",
  resource: "recurso", technology: "tecnología", event: "evento", observation: "observación",
  experience: "experiencia", question: "pregunta", hypothesis: "hipótesis",
  investigation: "investigación", evidence: "evidencia", decision: "decisión",
  outcome: "resultado", learning: "aprendizaje", fact: "hecho", insight: "hallazgo",
};

export function uniqueSources(tools: ToolRun[]): AssistantSource[] {
  const seen = new Map<string, AssistantSource>();
  for (const tool of tools) {
    for (const source of tool.sources) {
      if (!seen.has(source.node_id)) seen.set(source.node_id, source);
    }
  }
  return [...seen.values()];
}

function SourceNote({ source }: { source: AssistantSource }) {
  return (
    <li>
      <Link
        href={`/explain?node_id=${source.node_id}`}
        className="group block border-l-2 py-0.5 pl-2.5"
        style={{ borderColor: objectTypeColor(source.object_type) }}
      >
        <span className="block text-[0.8125rem] leading-snug text-ink group-hover:underline">{source.title}</span>
        {source.object_type && (
          <span className="text-xs text-ink-faint">{TYPE_LABELS[source.object_type] ?? source.object_type}</span>
        )}
      </Link>
    </li>
  );
}

/**
 * Notas al margen de una respuesta: qué consultó el asistente y qué nodos de la memoria
 * encontró. En pantallas anchas vive en el margen derecho, a la altura de la respuesta que
 * sustenta; en angostas se pliega debajo de ella.
 */
export function Marginalia({ tools, thinking }: { tools: ToolRun[]; thinking: string }) {
  const sources = uniqueSources(tools);
  const finished = tools.filter((t) => t.status !== "running");
  if (finished.length === 0 && !thinking) return null;

  return (
    <div className="space-y-4 text-[0.8125rem] leading-snug">
      {finished.length > 0 && (
        <ul className="space-y-1 text-ink-faint">
          {finished.map((tool) => (
            <li key={tool.id} className={tool.status === "error" ? "text-danger" : undefined}>
              {DONE_LABELS[tool.name] ?? tool.label}
              {tool.summary && <span className="block text-xs">{tool.summary}</span>}
            </li>
          ))}
        </ul>
      )}

      {sources.length > 0 && (
        <ul className="space-y-2.5">
          {sources.map((source) => (
            <SourceNote key={source.node_id} source={source} />
          ))}
        </ul>
      )}

      {thinking && (
        <details className="text-ink-faint">
          <summary className="cursor-pointer select-none hover:text-ink">Cómo lo pensó</summary>
          <p className="mt-1.5 whitespace-pre-wrap text-xs leading-relaxed">{thinking}</p>
        </details>
      )}
    </div>
  );
}
