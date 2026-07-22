"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { EvidenceTree } from "@/components/EvidenceTree";
import { ObjectTypeBadge } from "@/components/ObjectTypeBadge";
import { ApiError, explainEpisode, explainNode } from "@/lib/api-client";
import type { ExplainNodeResponse, ReasoningEpisodeDto } from "@/lib/types";

function EpisodeSummary({ episode }: { episode: ReasoningEpisodeDto }) {
  return (
    <li className="rounded-md border border-zinc-200 p-2 text-sm dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span className="font-medium text-zinc-900 dark:text-zinc-50">{episode.goal}</span>
        <span className="text-xs text-zinc-400">{episode.status}</span>
      </div>
      <p className="text-xs text-zinc-400">
        {episode.agent} · {new Date(episode.started_at).toLocaleString()} · {episode.steps.length} pasos
      </p>
      {episode.final_output && <p className="mt-1 text-zinc-600 dark:text-zinc-400">{episode.final_output}</p>}
    </li>
  );
}

function ExplainForm() {
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<"node" | "episode">("node");
  const [inputValue, setInputValue] = useState(searchParams.get("node_id") ?? "");
  const [nodeResult, setNodeResult] = useState<ExplainNodeResponse | null>(null);
  const [episodeResult, setEpisodeResult] = useState<Awaited<ReturnType<typeof explainEpisode>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function runExplain(id: string, explainMode: "node" | "episode") {
    if (!id.trim()) return;
    setIsLoading(true);
    setError(null);
    setNodeResult(null);
    setEpisodeResult(null);
    try {
      if (explainMode === "node") setNodeResult(await explainNode(id));
      else setEpisodeResult(await explainEpisode(id));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "No se pudo explicar.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const fromQuery = searchParams.get("node_id");
    // runExplain sets isLoading synchronously before its fetch; deep-link-on-mount from
    // NodeDetailPanel's "Ver razonamiento" link needs that same fetch-on-mount pattern as a
    // manual submit.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (fromQuery) runExplain(fromQuery, "node");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    runExplain(inputValue, mode);
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold text-zinc-900 dark:text-zinc-50">Visor de razonamiento</h1>
      <p className="mb-4 text-sm text-zinc-500 dark:text-zinc-400">
        ¿Cómo llegué a esta conclusión? Explora la evidencia (Pregunta → Investigación → … → Aprendizaje) detrás de un
        nodo, o la traza paso a paso de un episodio de razonamiento.
      </p>

      <form onSubmit={handleSubmit} className="mb-6 flex gap-2">
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as "node" | "episode")}
          className="rounded-md border border-zinc-300 px-2 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        >
          <option value="node">Nodo</option>
          <option value="episode">Episodio</option>
        </select>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder={mode === "node" ? "ID del nodo (UUID)" : "ID del episodio (UUID)"}
          className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm font-mono dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
        <button
          type="submit"
          disabled={isLoading}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {isLoading ? "Explicando…" : "Explicar"}
        </button>
      </form>

      <ErrorBanner message={error} />

      {nodeResult && (
        <div>
          <div className="mb-4 rounded-md border border-zinc-200 p-3 dark:border-zinc-800">
            <div className="mb-1 flex items-center gap-2">
              <ObjectTypeBadge objectType={nodeResult.object_type} />
              <span className="font-semibold text-zinc-900 dark:text-zinc-50">{nodeResult.title}</span>
            </div>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">{nodeResult.content}</p>
          </div>

          <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Evidencia de respaldo ({nodeResult.supporting_evidence.length})
          </h2>
          {nodeResult.supporting_evidence.length === 0 ? (
            <p className="mb-6 text-sm text-zinc-400 italic">Sin evidencia registrada.</p>
          ) : (
            <ul className="mb-6 space-y-2">
              {nodeResult.supporting_evidence.map((ev, i) => (
                <EvidenceTree key={`${ev.node_id}-${i}`} evidence={ev} depth={0} />
              ))}
            </ul>
          )}

          <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Episodios que lo produjeron/citaron ({nodeResult.episodes.length})
          </h2>
          {nodeResult.episodes.length === 0 ? (
            <p className="text-sm text-zinc-400 italic">Sin episodios asociados.</p>
          ) : (
            <ul className="space-y-2">
              {nodeResult.episodes.map((ep) => (
                <EpisodeSummary key={ep.id} episode={ep} />
              ))}
            </ul>
          )}
        </div>
      )}

      {episodeResult && (
        <div>
          <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Narrativa</h2>
          <ol className="mb-6 list-inside list-decimal space-y-1 text-sm text-zinc-700 dark:text-zinc-300">
            {episodeResult.narrative.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ol>

          <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Pasos ({episodeResult.episode.steps.length})
          </h2>
          <ul className="space-y-2">
            {episodeResult.episode.steps.map((step) => (
              <li key={step.id} className="rounded-md border border-zinc-200 p-2 text-sm dark:border-zinc-800">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-zinc-900 dark:text-zinc-50">
                    #{step.step_index} · {step.kind}
                    {step.capability_name && ` (${step.capability_name})`}
                  </span>
                  {step.approved !== null && (
                    <span className={step.approved ? "text-xs text-emerald-600" : "text-xs text-red-600"}>
                      {step.approved ? "aprobado" : "rechazado"}
                    </span>
                  )}
                </div>
                {step.input && <p className="mt-1 text-zinc-600 dark:text-zinc-400">→ {step.input}</p>}
                {step.output && <p className="mt-1 text-zinc-600 dark:text-zinc-400">← {step.output}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function ExplainPage() {
  return (
    <Suspense>
      <ExplainForm />
    </Suspense>
  );
}
