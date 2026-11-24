"use client";

import { useEffect, useId, useState } from "react";

import { Button, Card, EmptyState, ErrorNotice, MonoLabel, PageHeader, Skeleton } from "@/components/ui";
import { ApiError, listPendingApprovals, resolveApproval } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import type { ApprovalRequestDto } from "@/lib/types";

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.detail) return `${err.detail} ${fallback}`;
  return fallback;
}

function formatParam(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function InputsTable({ inputs }: { inputs: Record<string, unknown> }) {
  const captionId = useId();
  const entries = Object.entries(inputs);
  if (entries.length === 0) {
    return <p className="text-body-sm text-slate">Esta acción no lleva parámetros.</p>;
  }
  return (
    <div role="region" aria-labelledby={captionId} tabIndex={0} className="max-w-full overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <caption id={captionId} className="sr-only">
          Parámetros de la acción
        </caption>
        <thead>
          <tr>
            <th scope="col" className="border-b border-obsidian py-2 pr-4 text-left">
              <MonoLabel>Parámetro</MonoLabel>
            </th>
            <th scope="col" className="border-b border-obsidian py-2 text-left">
              <MonoLabel>Valor</MonoLabel>
            </th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, value]) => (
            <tr key={key}>
              <th scope="row" className="border-b border-hairline py-2 pr-4 align-top font-mono text-mono break-all text-obsidian">
                {key}
              </th>
              <td className="border-b border-hairline py-2 align-top text-body-sm break-all text-slate">
                {formatParam(value)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ApprovalsPage() {
  const { username } = useAuth();
  const [approvals, setApprovals] = useState<ApprovalRequestDto[] | null>(null);
  const [resolved, setResolved] = useState<Record<string, "approved" | "rejected">>({});
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [resolving, setResolving] = useState<{ id: string; approved: boolean } | null>(null);

  function load() {
    setIsLoading(true);
    setError(null);
    listPendingApprovals()
      .then((r) => {
        setApprovals(r.approvals);
        setResolved({});
      })
      .catch((err) => setError(describeError(err, "Actualiza la lista e inténtalo de nuevo.")))
      .finally(() => setIsLoading(false));
  }

  // Fetch-on-mount: el flag de carga debe reflejarse de inmediato al montar, antes de que
  // resuelva `listPendingApprovals`.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(load, []);

  async function handleResolve(id: string, approved: boolean) {
    setResolving({ id, approved });
    setError(null);
    try {
      await resolveApproval(id, approved, username ?? undefined);
      setResolved((prev) => ({ ...prev, [id]: approved ? "approved" : "rejected" }));
    } catch (err) {
      setError(describeError(err, "Inténtalo de nuevo."));
    } finally {
      setResolving(null);
    }
  }

  return (
    <div>
      <PageHeader
        title="Aprobaciones"
        continuation="lo que el agente espera de ti"
        description="Acciones que el agente detuvo hasta que tú las confirmes."
        actions={
          <Button type="button" variant="ghost" onClick={load} disabled={isLoading}>
            Actualizar
          </Button>
        }
      />

      {error && (
        <div className="mb-6">
          <ErrorNotice>{error}</ErrorNotice>
        </div>
      )}

      {isLoading && approvals === null && (
        <div aria-live="polite">
          <p className="text-caption text-slate">Cargando lo que espera tu aprobación. Espera un momento.</p>
          <Skeleton className="mt-3 h-36 w-full" />
          <Skeleton className="mt-3 h-36 w-full" />
        </div>
      )}

      {approvals && approvals.length === 0 && (
        <EmptyState
          title="No hay nada esperando tu aprobación."
          action={
            <Button type="button" variant="ghost" onClick={load} disabled={isLoading}>
              Actualizar
            </Button>
          }
        >
          Cuando el agente pause una acción, aparecerá aquí.
        </EmptyState>
      )}

      {approvals && approvals.length > 0 && (
        <ul className="space-y-4">
          {approvals.map((a) => {
            const outcome = resolved[a.id];
            const busy = resolving?.id === a.id;
            return (
              <Card as="li" key={a.id} className="min-w-0">
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <p className="font-mono text-mono text-obsidian">{a.capability_name}</p>
                  <p className="font-mono text-mono-sm text-muted">{new Date(a.created_at).toLocaleString("es")}</p>
                </div>
                <div className="mt-4">
                  <InputsTable inputs={a.inputs} />
                </div>
                <p className="mt-3 font-mono text-mono-sm text-muted">
                  episodio {a.episode_id.slice(0, 8)} · paso {a.step_id}
                  {a.reply_to && ` · aviso por ${a.reply_to.provider}`}
                </p>
                <div className="mt-4">
                  {outcome ? (
                    <p role="status" className="text-body-sm font-medium text-obsidian">
                      {outcome === "approved" ? "Aprobada" : "Rechazada"}
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" onClick={() => handleResolve(a.id, true)} disabled={busy}>
                        {busy && resolving?.approved ? "Guardando…" : "Aprobar"}
                      </Button>
                      <Button type="button" variant="ghost" onClick={() => handleResolve(a.id, false)} disabled={busy}>
                        {busy && resolving && !resolving.approved ? "Guardando…" : "Rechazar"}
                      </Button>
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </ul>
      )}
    </div>
  );
}
