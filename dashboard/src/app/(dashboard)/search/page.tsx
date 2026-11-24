"use client";

import { useId, useRef, useState, type FormEvent } from "react";

import { NodeDetailPanel } from "@/components/NodeDetailPanel";
import { ObjectTypeBadge } from "@/components/ObjectTypeBadge";
import { Badge, Button, EmptyState, ErrorNotice, MonoLabel, PageHeader, SectionTitle, Skeleton } from "@/components/ui";
import { ApiError, getContext, search } from "@/lib/api-client";
import type { ContextBundle, SearchKnowledgeResponse } from "@/lib/types";

const FIELD =
  "h-10 w-full rounded-md border border-hairline bg-paper px-3 text-body-sm text-obsidian placeholder:text-muted focus:border-obsidian";

// clip-path, no el recorte antiguo: si no, el aviso vivo sale del árbol de accesibilidad en algún navegador.
const VISUALLY_HIDDEN =
  "pointer-events-none absolute m-[-1px] h-px w-px overflow-hidden border-0 p-0 whitespace-nowrap [clip-path:inset(50%)]";

const STATUS_LABELS: Record<string, string> = {
  draft: "borrador",
  active: "activo",
  hypothesis: "hipótesis",
  fact: "hecho",
  superseded: "reemplazado",
  archived: "archivado",
};

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

function cardClass(selected: boolean): string {
  return `w-full rounded-md border bg-paper p-4 text-left hover:bg-wash sm:p-5 ${
    selected ? "border-obsidian" : "border-hairline"
  }`;
}

export default function SearchPage() {
  const queryId = useId();
  const limitId = useId();
  const queryRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(5);
  const [searchResults, setSearchResults] = useState<SearchKnowledgeResponse | null>(null);
  const [context, setContext] = useState<ContextBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!query.trim()) {
      queryRef.current?.setCustomValidity("Escribe una frase sobre el tema.");
      queryRef.current?.reportValidity();
      return;
    }
    queryRef.current?.setCustomValidity("");
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

  const announcement = !searchResults
    ? ""
    : searchResults.results.length === 0
      ? "No encontré nada con esas palabras."
      : `${searchResults.results.length} resultados.`;

  const nothingFound =
    searchResults !== null &&
    searchResults.results.length === 0 &&
    context !== null &&
    context.fragments.length === 0;

  return (
    <div className="flex flex-col gap-10 lg:flex-row lg:items-start">
      <div className="relative min-w-0 flex-1">
        <PageHeader
          title="Buscar"
          continuation="en todo lo que guardaste"
          description="Escribe unas palabras o una frase sobre lo que recuerdas."
        />

        <p className={VISUALLY_HIDDEN} aria-live="polite">
          {announcement}
        </p>

        <search aria-label="Buscar en lo que guardaste">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4 sm:flex-row sm:items-end">
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <label htmlFor={queryId} className="text-body-sm font-medium text-obsidian">
                Qué buscas
              </label>
              <input
                ref={queryRef}
                id={queryId}
                name="q"
                type="search"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  e.target.setCustomValidity("");
                }}
                onInvalid={(e) => e.currentTarget.setCustomValidity("Escribe una frase sobre el tema.")}
                placeholder="una frase sobre el tema"
                enterKeyHint="search"
                autoComplete="off"
                required
                className={FIELD}
              />
            </div>
            <div className="flex w-full flex-col gap-1.5 sm:w-32">
              <label htmlFor={limitId} className="text-body-sm font-medium text-obsidian">
                Cuántos
                <span className="mt-0.5 block text-caption font-normal text-slate">De 1 a 20</span>
              </label>
              <input
                id={limitId}
                name="limit"
                type="number"
                min={1}
                max={20}
                inputMode="numeric"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className={FIELD}
              />
            </div>
            <Button type="submit" disabled={isLoading} className="h-10 w-full sm:w-auto">
              {isLoading ? "Buscando…" : "Buscar"}
            </Button>
          </form>
        </search>

        {error && (
          <div className="mt-6">
            <ErrorNotice>{error} Revisa la conexión y vuelve a intentarlo.</ErrorNotice>
          </div>
        )}

        {isLoading && !searchResults && (
          <div className="mt-12 space-y-3" aria-busy="true">
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
          </div>
        )}

        {!searchResults && !isLoading && !error && (
          <div className="mt-12">
            <EmptyState
              title="Empieza con una frase"
              action={
                <Button type="button" variant="ghost" onClick={() => queryRef.current?.focus()}>
                  Escribir la búsqueda
                </Button>
              }
            >
              Describe el tema y pulsa Buscar.
            </EmptyState>
          </div>
        )}

        {nothingFound && !isLoading && (
          <div className="mt-12">
            <EmptyState
              title="No encontré nada con esas palabras."
              action={
                <Button type="button" variant="ghost" onClick={() => queryRef.current?.focus()}>
                  Probar otra frase
                </Button>
              }
            >
              Prueba describiendo el tema con una frase.
            </EmptyState>
          </div>
        )}

        {searchResults && searchResults.results.length > 0 && (
          <section className="mt-12">
            <SectionTitle aside={`${searchResults.results.length}`}>Resultados</SectionTitle>
            <ul className="space-y-3">
              {searchResults.results.map((r) => (
                <li key={r.node_id}>
                  <button
                    type="button"
                    onClick={() => setSelectedNodeId(r.node_id)}
                    aria-current={selectedNodeId === r.node_id ? "true" : undefined}
                    className={cardClass(selectedNodeId === r.node_id)}
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="min-w-0 flex-1 break-words text-body-sm font-medium text-obsidian">
                        {r.title}
                      </span>
                      <span className="shrink-0 font-mono text-mono-sm text-muted">
                        coincidencia {r.score.toFixed(3)}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 break-words text-body-sm text-slate">{r.content}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <ObjectTypeBadge objectType={r.object_type} />
                      <span className="font-mono text-mono-sm text-muted">confianza {r.confidence.toFixed(2)}</span>
                      <span className="font-mono text-mono-sm text-muted">importancia {r.importance.toFixed(2)}</span>
                      <span className="font-mono text-mono-sm text-muted">{statusLabel(r.status)}</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {context && context.fragments.length > 0 && (
          <section className="mt-16">
            <SectionTitle aside={`${context.fragments.length}`}>Contexto para citar</SectionTitle>
            <ul className="space-y-3">
              {context.fragments.map((f) => (
                <li key={`${f.node_id}-${f.version}`}>
                  <button
                    type="button"
                    onClick={() => setSelectedNodeId(f.node_id)}
                    aria-current={selectedNodeId === f.node_id ? "true" : undefined}
                    className={cardClass(selectedNodeId === f.node_id)}
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="min-w-0 flex-1 break-words text-body-sm font-medium text-obsidian">
                        [{f.citation_label}] {f.title}
                      </span>
                      {f.via_graph && <Badge tone="memoria">conectado</Badge>}
                    </div>
                    <p className="mt-2 line-clamp-2 break-words text-body-sm text-slate">{f.content}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <ObjectTypeBadge objectType={f.object_type} />
                      <span className="font-mono text-mono-sm text-muted">similitud {f.similarity.toFixed(2)}</span>
                      <span className="font-mono text-mono-sm text-muted">importancia {f.importance.toFixed(2)}</span>
                      <span className="font-mono text-mono-sm text-muted">confianza {f.confidence.toFixed(2)}</span>
                      <span className="font-mono text-mono-sm text-muted">recencia {f.recency.toFixed(2)}</span>
                      {f.source_id && (
                        <span className="font-mono text-mono-sm text-muted">fuente {f.source_id.slice(0, 8)}…</span>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>

            {context.relations_summary.length > 0 && (
              <div className="mt-10">
                <h3 className="mb-3">
                  <MonoLabel className="text-slate">Relaciones</MonoLabel>
                </h3>
                <ul className="space-y-2">
                  {context.relations_summary.map((r, i) => (
                    <li key={i} className="flex gap-3 text-body-sm text-slate">
                      <span aria-hidden="true" className="mt-2 h-0.5 w-4 shrink-0 bg-periwinkle" />
                      <span className="min-w-0 break-words">{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {context.timeline.length > 0 && (
              <div className="mt-10">
                <h3 className="mb-3">
                  <MonoLabel className="text-slate">Línea de tiempo</MonoLabel>
                </h3>
                <ul className="space-y-3">
                  {context.timeline.map((t) => (
                    <li key={`${t.node_id}-${t.version}`} className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span className="font-mono text-mono-sm text-muted">
                        {new Date(t.created_at).toLocaleString()}
                      </span>
                      <span className="min-w-0 break-words text-body-sm text-obsidian">{t.title}</span>
                      <span className="font-mono text-mono-sm text-muted">v{t.version}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        {searchResults &&
          searchResults.results.length > 0 &&
          context &&
          context.fragments.length === 0 && (
            <div className="mt-16">
              <EmptyState
                title="No hay contexto para citar con esas palabras."
                action={
                  <Button type="button" variant="ghost" onClick={() => queryRef.current?.focus()}>
                    Probar otra frase
                  </Button>
                }
              >
                Prueba una frase un poco más concreta.
              </EmptyState>
            </div>
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
