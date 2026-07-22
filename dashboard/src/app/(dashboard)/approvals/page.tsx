"use client";

import { useEffect, useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, listPendingApprovals, resolveApproval } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import type { ApprovalRequestDto } from "@/lib/types";

export default function ApprovalsPage() {
  const { username } = useAuth();
  const [approvals, setApprovals] = useState<ApprovalRequestDto[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  function load() {
    setIsLoading(true);
    setError(null);
    listPendingApprovals()
      .then((r) => setApprovals(r.approvals))
      .catch((err) => setError(err instanceof ApiError ? err.detail : "No se pudieron cargar las aprobaciones."))
      .finally(() => setIsLoading(false));
  }

  // Fetch-on-mount: el flag de carga debe reflejarse de inmediato al montar, antes de que
  // resuelva `listPendingApprovals`.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(load, []);

  async function handleResolve(id: string, approved: boolean) {
    setResolvingId(id);
    setError(null);
    try {
      await resolveApproval(id, approved, username ?? undefined);
      setApprovals((prev) => (prev ? prev.filter((a) => a.id !== id) : prev));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "No se pudo resolver la aprobación.");
    } finally {
      setResolvingId(null);
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Bandeja de aprobaciones</h1>
        <button onClick={load} className="text-sm text-blue-600 hover:underline dark:text-blue-400">
          Actualizar
        </button>
      </div>
      <p className="mb-4 text-sm text-zinc-500 dark:text-zinc-400">
        Capacidades sensibles que un agente pausó a mitad de razonamiento, a la espera de tu confirmación.
      </p>

      <ErrorBanner message={error} />
      {isLoading && <p className="text-sm text-zinc-500 dark:text-zinc-400">Cargando…</p>}

      {approvals && approvals.length === 0 && (
        <p className="text-sm italic text-zinc-400">No hay aprobaciones pendientes.</p>
      )}

      {approvals && approvals.length > 0 && (
        <ul className="space-y-3">
          {approvals.map((a) => (
            <li key={a.id} className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-medium text-zinc-900 dark:text-zinc-50">{a.capability_name}</span>
                <span className="text-xs text-zinc-400">{new Date(a.created_at).toLocaleString()}</span>
              </div>
              <pre className="mb-3 overflow-x-auto rounded bg-zinc-100 p-2 text-xs text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                {JSON.stringify(a.inputs, null, 2)}
              </pre>
              <p className="mb-3 text-xs text-zinc-400">
                episodio {a.episode_id.slice(0, 8)}… · paso #{a.step_id}
                {a.reply_to && ` · notificará por ${a.reply_to.provider}`}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleResolve(a.id, true)}
                  disabled={resolvingId === a.id}
                  className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                >
                  Aprobar
                </button>
                <button
                  onClick={() => handleResolve(a.id, false)}
                  disabled={resolvingId === a.id}
                  className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-50"
                >
                  Rechazar
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
