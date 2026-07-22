"use client";

import { useEffect, useMemo, useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, getNodeHistory, timeTravel } from "@/lib/api-client";
import { relationLabel } from "@/lib/object-type-style";
import type { GetNodeHistoryResponse, TimeTravelResponse } from "@/lib/types";

export default function TimelinePage() {
  const [inputValue, setInputValue] = useState("");
  const [nodeId, setNodeId] = useState("");
  const [history, setHistory] = useState<GetNodeHistoryResponse | null>(null);
  const [sliderMs, setSliderMs] = useState<number | null>(null);
  const [nowMs, setNowMs] = useState<number | null>(null);
  const [asOf, setAsOf] = useState<TimeTravelResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const bounds = useMemo(() => {
    if (!history || history.versions.length === 0 || nowMs === null) return null;
    const times = history.versions.map((v) => new Date(v.created_at).getTime());
    return { min: Math.min(...times), max: nowMs };
  }, [history, nowMs]);

  useEffect(() => {
    if (!nodeId) return;
    let cancelled = false;
    // Fetch-on-dependency-change: el flag de carga debe reflejarse apenas cambia `nodeId`,
    // antes de que resuelva el fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true);
    setError(null);
    getNodeHistory(nodeId)
      .then((h) => {
        if (cancelled) return;
        setHistory(h);
        // Date.now(), no la última versión: `created_at` viene del backend con precisión de
        // microsegundos, pero el `Date` de JS solo tiene milisegundos -- truncar y reconvertir a
        // ISO para el "at" enviado da un instante ligeramente ANTERIOR al real, y el backend
        // (created_at <= at) excluiría justo la última versión, mostrando la anterior por defecto.
        const now = Date.now();
        setSliderMs(now);
        setNowMs(now);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : "No se pudo cargar el historial.");
      })
      .finally(() => !cancelled && setIsLoading(false));
    return () => {
      cancelled = true;
    };
  }, [nodeId]);

  useEffect(() => {
    if (!nodeId || sliderMs === null) return;
    let cancelled = false;
    const at = new Date(sliderMs).toISOString();
    // Debounce: el slider dispara muchos eventos por segundo mientras se arrastra.
    const timeout = setTimeout(() => {
      timeTravel(nodeId, at, 1)
        .then((r) => !cancelled && setAsOf(r))
        .catch((err) => !cancelled && setError(err instanceof ApiError ? err.detail : "No se pudo viajar en el tiempo."));
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [nodeId, sliderMs]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (inputValue.trim()) setNodeId(inputValue.trim());
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold text-zinc-900 dark:text-zinc-50">Timeline</h1>

      <form onSubmit={handleSubmit} className="mb-6 flex gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="ID de nodo (UUID) — cópialo desde Búsqueda"
          className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm font-mono dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
        <button
          type="submit"
          disabled={isLoading}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {isLoading ? "Cargando…" : "Cargar"}
        </button>
      </form>

      <ErrorBanner message={error} />

      {history && (
        <section className="mb-8">
          <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Versiones capturadas ({history.versions.length})
          </h2>
          <ol className="space-y-2 border-l-2 border-zinc-200 pl-4 dark:border-zinc-800">
            {history.versions.map((v) => (
              <li key={v.version} className="relative">
                <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full bg-zinc-400" />
                <p className="text-xs text-zinc-400">{new Date(v.created_at).toLocaleString()}</p>
                <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50">v{v.version} · {v.title}</p>
              </li>
            ))}
          </ol>
        </section>
      )}

      {bounds && sliderMs !== null && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Viajar en el tiempo (&quot;as-of&quot;)</h2>
          <input
            type="range"
            min={bounds.min}
            max={bounds.max}
            value={sliderMs}
            onChange={(e) => setSliderMs(Number(e.target.value))}
            className="w-full"
          />
          <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">{new Date(sliderMs).toLocaleString()}</p>

          {asOf && (
            <div className="rounded-md border border-zinc-200 p-4 dark:border-zinc-800">
              {asOf.found && asOf.version ? (
                <>
                  <p className="mb-1 font-medium text-zinc-900 dark:text-zinc-50">
                    v{asOf.version.version} · {asOf.version.title}
                  </p>
                  <p className="mb-2 text-sm text-zinc-600 dark:text-zinc-400">{asOf.version.content}</p>
                  {asOf.relations.length > 0 && (
                    <ul className="text-xs text-zinc-500">
                      {asOf.relations.map((r, i) => (
                        <li key={i}>
                          {r.source_id === nodeId ? "→" : "←"} {relationLabel(r.relation_type)}{" "}
                          {(r.source_id === nodeId ? r.target_id : r.source_id).slice(0, 8)}…
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <p className="text-sm text-zinc-400 italic">El nodo aún no existía en ese instante.</p>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
