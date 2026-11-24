"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { EvidenceTree } from "@/components/EvidenceTree";
import { ObjectTypeBadge } from "@/components/ObjectTypeBadge";
import { Badge, Button, Card, EmptyState, ErrorNotice, PageHeader, SectionTitle, Skeleton } from "@/components/ui";
import { ApiError, explainEpisode, explainNode } from "@/lib/api-client";
import type { ExplainNodeResponse, ReasoningEpisodeDto } from "@/lib/types";

const INPUT_CLASS =
  "h-10 w-full min-w-0 rounded-md border border-hairline bg-paper px-3 text-body-sm text-obsidian placeholder:text-muted";

const EPISODE_STATUS: Record<string, string> = {
  running: "En curso",
  completed: "Terminado",
  failed: "No se completó",
  pending_approval: "Esperando tu aprobación",
  pending: "En espera",
};

const STEP_KIND: Record<string, string> = {
  plan: "Plan",
  execute: "Ejecución",
  review: "Revisión",
  replan: "Replanteo",
  conclude: "Conclusión",
};

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.detail) return `${err.detail} ${fallback}`;
  return fallback;
}

function EpisodeSummary({ episode }: { episode: ReasoningEpisodeDto }) {
  return (
    <Card as="li">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="text-body-sm font-medium text-obsidian">{episode.goal}</p>
        <Badge>{EPISODE_STATUS[episode.status] ?? episode.status}</Badge>
      </div>
      <p className="mt-2 font-mono text-mono-sm text-muted">
        {episode.agent} · {new Date(episode.started_at).toLocaleString("es")} · {episode.steps.length} pasos
      </p>
      {episode.final_output && <p className="mt-3 text-body-sm text-slate">{episode.final_output}</p>}
    </Card>
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
      setError(describeError(err, "Revisa el identificador e inténtalo de nuevo."));
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

  const idLabel = mode === "node" ? "Identificador del recuerdo" : "Identificador del episodio";

  return (
    <div>
      <form
        onSubmit={handleSubmit}
        aria-label="Explicar un recuerdo o un episodio"
        className="flex flex-col gap-4 sm:flex-row sm:items-end"
      >
        <div className="flex flex-col gap-1 sm:w-48">
          <label htmlFor="explain-mode" className="text-caption text-slate">
            Qué explicar
          </label>
          <select
            id="explain-mode"
            value={mode}
            onChange={(e) => setMode(e.target.value as "node" | "episode")}
            className={INPUT_CLASS}
          >
            <option value="node">Un recuerdo</option>
            <option value="episode">Un episodio</option>
          </select>
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <label htmlFor="explain-id" className="text-caption text-slate">
            {idLabel}
          </label>
          <input
            id="explain-id"
            type="text"
            required
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={mode === "node" ? "Cópialo desde Búsqueda" : "Cópialo del episodio"}
            spellCheck={false}
            autoCapitalize="off"
            enterKeyHint="search"
            className={`${INPUT_CLASS} font-mono text-mono`}
          />
        </div>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Explicando…" : "Explicar"}
        </Button>
      </form>

      {error && (
        <div className="mt-6">
          <ErrorNotice>{error}</ErrorNotice>
        </div>
      )}

      {isLoading && (
        <div className="mt-8" aria-live="polite">
          <p className="text-caption text-slate">Buscando la explicación. Espera un momento.</p>
          <Skeleton className="mt-3 h-24 w-full" />
          <Skeleton className="mt-3 h-40 w-full" />
        </div>
      )}

      {nodeResult && (
        <div className="mt-12">
          <Card>
            <div className="flex flex-wrap items-center gap-2">
              <ObjectTypeBadge objectType={nodeResult.object_type} />
              <h2 className="text-subheading font-medium text-obsidian">{nodeResult.title}</h2>
            </div>
            {nodeResult.content && (
              <p className="mt-3 whitespace-pre-wrap text-body-sm text-slate">{nodeResult.content}</p>
            )}
          </Card>

          <div className="mt-12">
            <SectionTitle aside={String(nodeResult.supporting_evidence.length)}>Evidencia de respaldo</SectionTitle>
            {nodeResult.supporting_evidence.length === 0 ? (
              <EmptyState
                title="No hay evidencia registrada."
                action={
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => document.getElementById("explain-id")?.focus()}
                  >
                    Probar otro identificador
                  </Button>
                }
              >
                Este recuerdo no tiene notas de respaldo. Prueba con otro identificador.
              </EmptyState>
            ) : (
              <ul className="space-y-2">
                {nodeResult.supporting_evidence.map((ev, i) => (
                  <EvidenceTree key={`${ev.node_id}-${i}`} evidence={ev} depth={0} />
                ))}
              </ul>
            )}
          </div>

          <div className="mt-12">
            <SectionTitle aside={String(nodeResult.episodes.length)}>Episodios que lo produjeron o citaron</SectionTitle>
            {nodeResult.episodes.length === 0 ? (
              <EmptyState
                title="No hay episodios asociados."
                action={
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => document.getElementById("explain-id")?.focus()}
                  >
                    Probar otro identificador
                  </Button>
                }
              >
                Ningún razonamiento guardado produjo o citó este recuerdo.
              </EmptyState>
            ) : (
              <ul className="space-y-3">
                {nodeResult.episodes.map((ep) => (
                  <EpisodeSummary key={ep.id} episode={ep} />
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {episodeResult && (
        <div className="mt-12">
          <SectionTitle aside={String(episodeResult.narrative.length)}>Narrativa</SectionTitle>
          {episodeResult.narrative.length === 0 ? (
            <EmptyState
              title="Este episodio no tiene narrativa."
              action={
                <Button type="button" variant="ghost" onClick={() => document.getElementById("explain-id")?.focus()}>
                  Probar otro identificador
                </Button>
              }
            >
              Revisa los pasos de abajo o prueba con otro identificador.
            </EmptyState>
          ) : (
            <ol className="list-decimal space-y-2 pl-5 text-body-sm text-obsidian">
              {episodeResult.narrative.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ol>
          )}

          <div className="mt-12">
            <SectionTitle aside={String(episodeResult.episode.steps.length)}>Pasos</SectionTitle>
            {episodeResult.episode.steps.length === 0 ? (
              <EmptyState
                title="Este episodio no tiene pasos."
                action={
                  <Button type="button" variant="ghost" onClick={() => document.getElementById("explain-id")?.focus()}>
                    Probar otro identificador
                  </Button>
                }
              >
                Puede que se haya cerrado antes de registrar el razonamiento.
              </EmptyState>
            ) : (
              <ul className="space-y-3">
                {episodeResult.episode.steps.map((step) => (
                  <Card as="li" key={step.id}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-body-sm font-medium text-obsidian">
                        Paso {step.step_index} · {STEP_KIND[step.kind] ?? step.kind}
                        {step.capability_name && (
                          <span className="ml-2 font-mono text-mono font-normal text-slate">
                            {step.capability_name}
                          </span>
                        )}
                      </p>
                      {step.approved === true && <Badge>Aprobado</Badge>}
                      {step.approved === false && <Badge>Rechazado</Badge>}
                    </div>
                    {step.input && (
                      <p className="mt-3 text-body-sm text-slate">
                        <span className="mono-label mr-2 text-muted">Entrada</span>
                        {step.input}
                      </p>
                    )}
                    {step.output && (
                      <p className="mt-2 text-body-sm text-slate">
                        <span className="mono-label mr-2 text-muted">Salida</span>
                        {step.output}
                      </p>
                    )}
                  </Card>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ExplainFallback() {
  return (
    <div aria-live="polite">
      <p className="text-caption text-slate">Cargando el formulario. Espera un momento.</p>
      <Skeleton className="mt-3 h-10 w-full" />
    </div>
  );
}

export default function ExplainPage() {
  return (
    <div>
      <PageHeader
        title="Razonamiento"
        continuation="de dónde sale cada conclusión"
        description="Pega un identificador y mira la evidencia que sostiene esa conclusión."
      />
      <Suspense fallback={<ExplainFallback />}>
        <ExplainForm />
      </Suspense>
    </div>
  );
}
