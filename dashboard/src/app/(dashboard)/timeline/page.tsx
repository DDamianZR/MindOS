"use client";

import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";

import { ObjectTypeBadge } from "@/components/ObjectTypeBadge";
import { Button, Card, EmptyState, ErrorNotice, PageHeader, SectionTitle, Skeleton } from "@/components/ui";
import { ApiError, getNodeHistory, timeTravel } from "@/lib/api-client";
import { relationLabel } from "@/lib/object-type-style";
import type { GetNodeHistoryResponse, TimeTravelResponse } from "@/lib/types";

const FIELD =
  "h-10 w-full rounded-md border border-hairline bg-paper px-3 font-mono text-body-sm text-obsidian placeholder:text-muted focus:border-obsidian";

export default function TimelinePage() {
  const nodeFieldId = useId();
  const nodeHintId = useId();
  const sliderId = useId();
  const nodeInputRef = useRef<HTMLInputElement>(null);
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

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const id = inputValue.trim();
    if (!id) {
      nodeInputRef.current?.setCustomValidity("Escribe el identificador de una nota.");
      nodeInputRef.current?.reportValidity();
      return;
    }
    nodeInputRef.current?.setCustomValidity("");
    setNodeId(id);
  }

  return (
    <div>
      <PageHeader
        title="Línea de tiempo"
        continuation="lo que pensabas en cada momento"
        description="Recorre las versiones de una nota y mira cómo estaba en cada momento."
      />

      <form onSubmit={handleSubmit} className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <label htmlFor={nodeFieldId} className="text-body-sm font-medium text-obsidian">
            Identificador
          </label>
          <p id={nodeHintId} className="text-caption text-slate">
            Lo encuentras al abrir un resultado en Buscar.
          </p>
          <input
            ref={nodeInputRef}
            id={nodeFieldId}
            name="node_id"
            type="text"
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              e.target.setCustomValidity("");
            }}
            onInvalid={(e) => e.currentTarget.setCustomValidity("Escribe el identificador de una nota.")}
            placeholder="pega aquí el identificador"
            aria-describedby={nodeHintId}
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            autoComplete="off"
            enterKeyHint="go"
            required
            className={FIELD}
          />
        </div>
        <Button type="submit" disabled={isLoading} className="h-10 w-full sm:w-auto">
          {isLoading ? "Cargando…" : "Cargar"}
        </Button>
      </form>

      {error && (
        <div className="mt-6">
          <ErrorNotice>{error} Revisa la conexión y vuelve a intentarlo.</ErrorNotice>
        </div>
      )}

      {isLoading && !history && (
        <div className="mt-12 space-y-3" aria-busy="true">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      )}

      {!nodeId && !history && !isLoading && !error && (
        <div className="mt-12">
          <EmptyState
            title="Todavía no hay una línea de tiempo"
            action={
              <Button type="button" variant="ghost" onClick={() => nodeInputRef.current?.focus()}>
                Escribir el identificador
              </Button>
            }
          >
            Pega el identificador de una nota. Lo encuentras al abrir un resultado en Buscar.
          </EmptyState>
        </div>
      )}

      {history && history.versions.length === 0 && !isLoading && (
        <div className="mt-12">
          <EmptyState
            title="Esta nota no tiene versiones."
            action={
              <Button type="button" variant="ghost" onClick={() => nodeInputRef.current?.focus()}>
                Probar otro identificador
              </Button>
            }
          >
            Revisa el identificador y vuelve a cargarla.
          </EmptyState>
        </div>
      )}

      {history && history.versions.length > 0 && (
        <section className="mt-12">
          <SectionTitle aside={`${history.versions.length} guardadas`}>Versiones</SectionTitle>
          <div className="mb-5">
            <ObjectTypeBadge objectType={history.object_type} />
          </div>
          <ol className="space-y-6">
            {history.versions.map((v) => (
              <li key={v.version} className="border-l border-hairline pl-4">
                <span aria-hidden="true" className="mb-2 block h-0.5 w-4 bg-periwinkle" />
                <p className="font-mono text-mono-sm text-muted">{new Date(v.created_at).toLocaleString()}</p>
                <p className="mt-1 break-words text-body-sm font-medium text-obsidian">
                  v{v.version} · {v.title}
                </p>
              </li>
            ))}
          </ol>
        </section>
      )}

      {bounds && sliderMs !== null && (
        <section className="mt-16">
          <SectionTitle>En ese momento</SectionTitle>
          <label htmlFor={sliderId} className="mb-1.5 block text-body-sm font-medium text-obsidian">
            Momento
          </label>
          <input
            id={sliderId}
            type="range"
            min={bounds.min}
            max={bounds.max}
            value={sliderMs}
            onChange={(e) => setSliderMs(Number(e.target.value))}
            aria-valuetext={new Date(sliderMs).toLocaleString()}
            className="h-10 w-full accent-obsidian scheme-light"
            style={{ accentColor: "#000000" }}
          />
          <p className="mt-2 mb-6 font-mono text-mono-sm text-muted">{new Date(sliderMs).toLocaleString()}</p>

          {asOf && asOf.found && asOf.version ? (
            <Card>
              <p className="break-words text-body-sm font-medium text-obsidian">
                v{asOf.version.version} · {asOf.version.title}
              </p>
              <p className="mt-2 break-words text-body-sm text-slate">{asOf.version.content}</p>
              {asOf.relations.length > 0 && (
                <ul className="mt-4 space-y-2">
                  {asOf.relations.map((r, i) => (
                    <li key={i} className="break-all font-mono text-mono-sm text-muted">
                      {r.source_id === nodeId ? "→" : "←"} {relationLabel(r.relation_type)}{" "}
                      {(r.source_id === nodeId ? r.target_id : r.source_id).slice(0, 8)}…
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          ) : asOf ? (
            <EmptyState
              title="En ese momento esta nota todavía no existía."
              action={
                <Button type="button" variant="ghost" onClick={() => setSliderMs(bounds.max)}>
                  Ir a hoy
                </Button>
              }
            >
              Mueve el control hacia hoy.
            </EmptyState>
          ) : null}
        </section>
      )}
    </div>
  );
}
