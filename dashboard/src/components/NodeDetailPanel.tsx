"use client";

import { useEffect, useState } from "react";

import { ApiError, getNodeHistory, getNodeNeighbors, getNodeProvenance } from "@/lib/api-client";
import type { GetNodeHistoryResponse, GetNodeNeighborsResponse, GetNodeProvenanceResponse } from "@/lib/types";
import { relationLabel } from "@/lib/object-type-style";

import { ObjectTypeBadge } from "./ObjectTypeBadge";
import { Button, ButtonLink, Card, EmptyState, ErrorNotice, SectionTitle, Skeleton } from "./ui";

interface Props {
  nodeId: string;
  onClose: () => void;
  /** Si se provee, los vecinos se vuelven clicables para re-centrar el panel en ellos. */
  onNavigate?: (nodeId: string) => void;
}

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
    <aside
      aria-label="Detalle de la nota"
      className="flex w-full min-w-0 shrink-0 flex-col overflow-y-auto border-l border-hairline bg-paper p-5 lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:w-96 lg:self-start"
    >
      <div className="mb-6 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-all font-mono text-mono-sm text-muted">{nodeId}</p>
          {latest && (
            <p className="mt-2 break-words text-subheading font-medium text-obsidian">{latest.title}</p>
          )}
        </div>
        <Button type="button" variant="ghost" onClick={onClose} className="shrink-0">
          Cerrar
        </Button>
      </div>

      {error && (
        <div className="mb-6">
          <ErrorNotice>{error} Revisa la conexión y vuelve a intentarlo.</ErrorNotice>
        </div>
      )}

      {isLoading && (
        <div className="mb-6 space-y-3" aria-busy="true">
          <Skeleton className="h-6 w-24" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {history && (
        <div className="mb-5">
          <ObjectTypeBadge objectType={history.object_type} />
        </div>
      )}

      <div className="mb-8">
        <ButtonLink href={`/explain?node_id=${nodeId}`} variant="ghost">
          Ver cómo llegué a esto
        </ButtonLink>
      </div>

      {history && (
        <section className="mb-10">
          <SectionTitle aside={`${history.versions.length}`}>Versiones</SectionTitle>
          {history.versions.length === 0 ? (
            <EmptyState title="Esta nota no tiene versiones.">
              Prueba con otro identificador.
            </EmptyState>
          ) : (
            <ul className="space-y-3">
              {[...history.versions].reverse().map((v) => (
                <Card as="li" key={v.version}>
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="min-w-0 break-words text-body-sm font-medium text-obsidian">
                      v{v.version} · {v.title}
                    </p>
                    <p className="font-mono text-mono-sm text-muted">{new Date(v.created_at).toLocaleString()}</p>
                  </div>
                  <p className="mt-2 line-clamp-2 break-words text-body-sm text-slate">{v.content}</p>
                  <p className="mt-3 break-words font-mono text-mono-sm text-muted">
                    autor {v.author} · confianza {v.confidence.toFixed(2)} · importancia {v.importance.toFixed(2)} ·{" "}
                    {statusLabel(v.status)}
                  </p>
                </Card>
              ))}
            </ul>
          )}
        </section>
      )}

      {provenance && (
        <section className="mb-10">
          <SectionTitle>Procedencia</SectionTitle>
          <ul className="space-y-3">
            {provenance.chain.map((p) => (
              <Card as="li" key={p.version}>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="text-body-sm font-medium text-obsidian">
                    v{p.version} · {p.author}
                  </p>
                  <p className="font-mono text-mono-sm text-muted">{new Date(p.created_at).toLocaleString()}</p>
                </div>
                {p.source ? (
                  <p className="mt-2 break-all font-mono text-mono-sm text-muted">
                    origen {p.source.kind}
                    {p.source.uri ? ` · ${p.source.uri}` : ""}
                  </p>
                ) : (
                  <p className="mt-2 font-mono text-mono-sm text-muted">sin origen registrado</p>
                )}
              </Card>
            ))}
          </ul>
        </section>
      )}

      {directNeighbors && (
        <section>
          <SectionTitle aside={`${directNeighbors.length}`}>Conexiones</SectionTitle>
          {directNeighbors.length === 0 ? (
            <EmptyState title="Sin conexiones">Esta nota no enlaza con otras.</EmptyState>
          ) : (
            <ul className="space-y-3">
              {directNeighbors.map((edge, i) => {
                const isOutgoing = edge.source_id === nodeId;
                const otherId = isOutgoing ? edge.target_id : edge.source_id;
                return (
                  <li
                    key={`${edge.source_id}-${edge.target_id}-${edge.relation_type}-${i}`}
                    className="flex flex-wrap items-baseline gap-x-2 gap-y-1"
                  >
                    <span className="font-mono text-mono-sm text-muted">{isOutgoing ? "→" : "←"}</span>
                    <span className="text-body-sm text-slate">{relationLabel(edge.relation_type)}</span>
                    {onNavigate ? (
                      <button
                        type="button"
                        onClick={() => onNavigate(otherId)}
                        className="break-all text-left font-mono text-mono-sm text-obsidian underline decoration-periwinkle decoration-2 underline-offset-2"
                      >
                        {otherId}
                      </button>
                    ) : (
                      <span className="break-all font-mono text-mono-sm text-muted">{otherId}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}
    </aside>
  );
}
