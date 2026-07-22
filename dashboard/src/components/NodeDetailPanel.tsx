"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, getNodeHistory, getNodeNeighbors, getNodeProvenance } from "@/lib/api-client";
import type { GetNodeHistoryResponse, GetNodeNeighborsResponse, GetNodeProvenanceResponse } from "@/lib/types";
import { relationLabel } from "@/lib/object-type-style";

import { ErrorBanner } from "./ErrorBanner";
import { ObjectTypeBadge } from "./ObjectTypeBadge";

interface Props {
  nodeId: string;
  onClose: () => void;
  /** Si se provee, los vecinos se vuelven clicables para re-centrar el panel en ellos. */
  onNavigate?: (nodeId: string) => void;
}

export function NodeDetailPanel({ nodeId, onClose, onNavigate }: Props) {
  const [history, setHistory] = useState<GetNodeHistoryResponse | null>(null);
  const [provenance, setProvenance] = useState<GetNodeProvenanceResponse | null>(null);
  const [neighbors, setNeighbors] = useState<GetNodeNeighborsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    // Fetch-on-dependency-change: el flag de carga debe reflejarse apenas cambia `nodeId`,
    // antes de que resuelvan los fetches.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true);
    setError(null);
    // depth=1 a propósito: /neighbors con depth>1 devuelve el subgrafo recursivo completo,
    // incluidas aristas que no tocan `nodeId` (p.ej. un vecino-de-vecino) -- una lista plana
    // como esta solo puede representar con sentido las relaciones DIRECTAS del nodo centrado;
    // el subgrafo multi-salto es lo que renderiza el Grafo (Cytoscape), no este panel.
    Promise.all([getNodeHistory(nodeId), getNodeProvenance(nodeId), getNodeNeighbors(nodeId, 1)])
      .then(([h, p, n]) => {
        if (cancelled) return;
        setHistory(h);
        setProvenance(p);
        setNeighbors(n);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : "No se pudo cargar el nodo.");
      })
      .finally(() => !cancelled && setIsLoading(false));
    return () => {
      cancelled = true;
    };
  }, [nodeId]);

  const latest = history?.versions[history.versions.length - 1];
  // depth=1 (ver el fetch más arriba) ya solo debería devolver aristas que tocan `nodeId`, pero
  // se filtra explícito -- renderizar una arista que no lo toca como si lo hiciera sería engañoso.
  const directNeighbors = neighbors?.neighbors.filter((e) => e.source_id === nodeId || e.target_id === nodeId);

  return (
    <aside className="flex h-full w-96 shrink-0 flex-col overflow-y-auto border-l border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-mono text-xs text-zinc-400">{nodeId}</p>
          {latest && <h2 className="truncate text-base font-semibold text-zinc-900 dark:text-zinc-50">{latest.title}</h2>}
        </div>
        <button onClick={onClose} className="shrink-0 text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
          Cerrar
        </button>
      </div>

      <ErrorBanner message={error} />
      {isLoading && <p className="text-sm text-zinc-500 dark:text-zinc-400">Cargando…</p>}

      {latest && (
        <div className="mb-2">
          <ObjectTypeBadge objectType={history?.object_type} />
        </div>
      )}

      <Link
        href={`/explain?node_id=${nodeId}`}
        className="mb-4 inline-block text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
      >
        Ver razonamiento (¿cómo llegué a esto?) →
      </Link>

      {history && (
        <section className="mb-6">
          <h3 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Versiones ({history.versions.length})
          </h3>
          <ul className="space-y-2">
            {[...history.versions].reverse().map((v) => (
              <li key={v.version} className="rounded-md border border-zinc-200 p-2 text-sm dark:border-zinc-800">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-zinc-900 dark:text-zinc-50">v{v.version} · {v.title}</span>
                  <span className="text-xs text-zinc-400">{new Date(v.created_at).toLocaleString()}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-zinc-600 dark:text-zinc-400">{v.content}</p>
                <div className="mt-1 flex gap-3 text-xs text-zinc-400">
                  <span>autor: {v.author}</span>
                  <span>confianza: {v.confidence.toFixed(2)}</span>
                  <span>importancia: {v.importance.toFixed(2)}</span>
                  <span>estado: {v.status}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {provenance && (
        <section className="mb-6">
          <h3 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Procedencia</h3>
          <ul className="space-y-2">
            {provenance.chain.map((p) => (
              <li key={p.version} className="rounded-md border border-zinc-200 p-2 text-sm dark:border-zinc-800">
                <div className="flex justify-between">
                  <span>v{p.version} · {p.author}</span>
                  <span className="text-xs text-zinc-400">{new Date(p.created_at).toLocaleString()}</span>
                </div>
                {p.source ? (
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                    origen: {p.source.kind}{p.source.uri ? ` · ${p.source.uri}` : ""}
                  </p>
                ) : (
                  <p className="mt-1 text-xs text-zinc-400 italic">sin origen registrado</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {directNeighbors && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Vecinos ({directNeighbors.length})
          </h3>
          {directNeighbors.length === 0 && <p className="text-sm text-zinc-400 italic">Sin relaciones registradas.</p>}
          <ul className="space-y-1">
            {directNeighbors.map((edge, i) => {
              const isOutgoing = edge.source_id === nodeId;
              const otherId = isOutgoing ? edge.target_id : edge.source_id;
              return (
                <li key={`${edge.source_id}-${edge.target_id}-${edge.relation_type}-${i}`} className="text-sm">
                  <span className="text-zinc-400">{isOutgoing ? "→" : "←"}</span>{" "}
                  <span className="text-zinc-600 dark:text-zinc-400">{relationLabel(edge.relation_type)}</span>{" "}
                  {onNavigate ? (
                    <button
                      onClick={() => onNavigate(otherId)}
                      className="font-mono text-xs text-blue-600 hover:underline dark:text-blue-400"
                    >
                      {otherId}
                    </button>
                  ) : (
                    <span className="font-mono text-xs text-zinc-500">{otherId}</span>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </aside>
  );
}
