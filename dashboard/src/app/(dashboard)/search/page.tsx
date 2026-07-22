"use client";

import { useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { NodeDetailPanel } from "@/components/NodeDetailPanel";
import { ObjectTypeBadge } from "@/components/ObjectTypeBadge";
import { ApiError, getContext, search } from "@/lib/api-client";
import type { ContextBundle, SearchKnowledgeResponse } from "@/lib/types";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(5);
  const [searchResults, setSearchResults] = useState<SearchKnowledgeResponse | null>(null);
  const [context, setContext] = useState<ContextBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      const [s, c] = await Promise.all([search(query, limit), getContext(query, limit, 1)]);
      setSearchResults(s);
      setContext(c);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "No se pudo buscar.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex h-full gap-6">
      <div className="min-w-0 flex-1 overflow-y-auto">
        <h1 className="mb-4 text-xl font-semibold text-zinc-900 dark:text-zinc-50">Búsqueda</h1>

        <form onSubmit={handleSubmit} className="mb-6 flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="¿Qué estás buscando?"
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <input
            type="number"
            min={1}
            max={20}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            title="Límite de resultados"
            className="w-20 rounded-md border border-zinc-300 px-2 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <button
            type="submit"
            disabled={isLoading}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {isLoading ? "Buscando…" : "Buscar"}
          </button>
        </form>

        <ErrorBanner message={error} />

        {searchResults && (
          <section className="mb-8">
            <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Resultados ({searchResults.results.length})
            </h2>
            <ul className="space-y-2">
              {searchResults.results.map((r) => (
                <li key={r.node_id}>
                  <button
                    onClick={() => setSelectedNodeId(r.node_id)}
                    className="w-full rounded-md border border-zinc-200 p-3 text-left text-sm hover:border-zinc-400 dark:border-zinc-800 dark:hover:border-zinc-600"
                  >
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="font-medium text-zinc-900 dark:text-zinc-50">{r.title}</span>
                      <span className="shrink-0 text-xs text-zinc-400">score {r.score.toFixed(3)}</span>
                    </div>
                    <p className="mb-1 line-clamp-2 text-zinc-600 dark:text-zinc-400">{r.content}</p>
                    <div className="flex items-center gap-2 text-xs text-zinc-400">
                      <ObjectTypeBadge objectType={r.object_type} />
                      <span>confianza {r.confidence.toFixed(2)}</span>
                      <span>importancia {r.importance.toFixed(2)}</span>
                      <span>{r.status}</span>
                    </div>
                  </button>
                </li>
              ))}
              {searchResults.results.length === 0 && (
                <p className="text-sm text-zinc-400 italic">Sin resultados.</p>
              )}
            </ul>
          </section>
        )}

        {context && (
          <section>
            <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Contexto citable (GraphRAG)</h2>
            <ul className="mb-4 space-y-2">
              {context.fragments.map((f) => (
                <li key={`${f.node_id}-${f.version}`}>
                  <button
                    onClick={() => setSelectedNodeId(f.node_id)}
                    className="w-full rounded-md border border-zinc-200 p-3 text-left text-sm hover:border-zinc-400 dark:border-zinc-800 dark:hover:border-zinc-600"
                  >
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="font-medium text-zinc-900 dark:text-zinc-50">
                        [{f.citation_label}] {f.title}
                      </span>
                      {f.via_graph && <span className="shrink-0 text-xs text-indigo-500">vía grafo</span>}
                    </div>
                    <p className="mb-1 line-clamp-2 text-zinc-600 dark:text-zinc-400">{f.content}</p>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                      <ObjectTypeBadge objectType={f.object_type} />
                      <span>similitud {f.similarity.toFixed(2)}</span>
                      <span>importancia {f.importance.toFixed(2)}</span>
                      <span>confianza {f.confidence.toFixed(2)}</span>
                      <span>recencia {f.recency.toFixed(2)}</span>
                      {f.source_id && <span>fuente {f.source_id.slice(0, 8)}…</span>}
                    </div>
                  </button>
                </li>
              ))}
              {context.fragments.length === 0 && <p className="text-sm text-zinc-400 italic">Sin fragmentos.</p>}
            </ul>

            {context.relations_summary.length > 0 && (
              <div className="mb-4">
                <h3 className="mb-1 text-xs font-semibold uppercase text-zinc-500">Relaciones</h3>
                <ul className="list-inside list-disc text-sm text-zinc-600 dark:text-zinc-400">
                  {context.relations_summary.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}

            {context.timeline.length > 0 && (
              <div>
                <h3 className="mb-1 text-xs font-semibold uppercase text-zinc-500">Línea temporal</h3>
                <ul className="text-sm text-zinc-600 dark:text-zinc-400">
                  {context.timeline.map((t) => (
                    <li key={`${t.node_id}-${t.version}`}>
                      {new Date(t.created_at).toLocaleString()} · {t.title} (v{t.version})
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </div>

      {selectedNodeId && (
        <NodeDetailPanel
          nodeId={selectedNodeId}
          onClose={() => setSelectedNodeId(null)}
          onNavigate={setSelectedNodeId}
        />
      )}
    </div>
  );
}
