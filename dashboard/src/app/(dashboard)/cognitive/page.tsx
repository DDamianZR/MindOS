"use client";

import { useEffect, useRef, useState } from "react";

import { EvidenceTree } from "@/components/EvidenceTree";
import { ObjectTypeBadge } from "@/components/ObjectTypeBadge";
import {
  Badge,
  Button,
  ButtonLink,
  Card,
  EmptyState,
  ErrorNotice,
  MonoLabel,
  PageHeader,
  SectionTitle,
  Skeleton,
  formatNumber,
} from "@/components/ui";
import {
  ApiError,
  contradictionsByTopic,
  decisions,
  patterns,
  pastThinking,
  similarIdeas,
  support,
} from "@/lib/api-client";
import type {
  ContradictionPair,
  ContradictionsResponse,
  DecisionsResponse,
  PastThinkingResponse,
  PatternsResponse,
  SimilarIdeasResponse,
  SupportResponse,
} from "@/lib/types";

const INPUT_CLASS =
  "h-10 w-full min-w-0 rounded-md border border-hairline bg-paper px-3 text-body-sm text-obsidian placeholder:text-muted";

const QUESTIONS = [
  { id: "fecha", label: "En una fecha", question: "¿Qué pensaba en una fecha sobre un tema?" },
  { id: "similares", label: "Ideas similares", question: "¿Qué ideas similares tuve antes?" },
  { id: "decisiones", label: "Decisiones", question: "¿Qué decisiones tomé y por qué?" },
  { id: "respaldo", label: "Respaldo", question: "¿Qué respalda esta recomendación?" },
  { id: "contradicciones", label: "Contradicciones", question: "¿Qué contradicciones hay en lo que sé?" },
  { id: "patrones", label: "Patrones", question: "¿Qué patrones aparecen en mi forma de pensar?" },
  { id: "conclusion", label: "Conclusión", question: "¿Cómo llegué a esta conclusión?" },
] as const;

type QuestionId = (typeof QUESTIONS)[number]["id"];

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.detail) return `${err.detail} ${fallback}`;
  return fallback;
}

function useAsync<T>() {
  const [result, setResult] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  async function run(fn: () => Promise<T>) {
    setIsLoading(true);
    setError(null);
    try {
      setResult(await fn());
    } catch (err) {
      setError(describeError(err, "Revisa los datos e inténtalo de nuevo."));
    } finally {
      setIsLoading(false);
    }
  }
  return { result, error, isLoading, run };
}

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1">
      <label htmlFor={id} className="text-caption text-slate">
        {label}
      </label>
      {children}
    </div>
  );
}

function QueryStatus({ loading }: { loading: boolean }) {
  if (!loading) return null;
  return (
    <div className="mt-4" aria-live="polite">
      <p className="text-caption text-slate">Consultando tu memoria. Espera un momento.</p>
      <Skeleton className="mt-3 h-24 w-full" />
    </div>
  );
}

function QueryError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="mt-4">
      <ErrorNotice>{message}</ErrorNotice>
    </div>
  );
}

function ContradictionCard({ pair }: { pair: ContradictionPair }) {
  return (
    <Card as="li">
      <Badge tone="pensamiento">Contradicción</Badge>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div className="min-w-0 sm:border-r sm:border-hairline sm:pr-4">
          <MonoLabel>Una idea</MonoLabel>
          <p className="mt-2 text-body-sm text-obsidian">{pair.node_a_title}</p>
        </div>
        <div className="min-w-0">
          <MonoLabel>La otra</MonoLabel>
          <p className="mt-2 text-body-sm text-obsidian">{pair.node_b_title}</p>
        </div>
      </div>
      {pair.rationale && <p className="mt-4 text-caption text-slate">{pair.rationale}</p>}
      {pair.confidence !== null && (
        <p className="mt-3 font-mono text-mono-sm text-muted">confianza {pair.confidence.toFixed(2)}</p>
      )}
    </Card>
  );
}

function PastThinkingWidget({ headingId }: { headingId: string }) {
  const [topic, setTopic] = useState("");
  const [at, setAt] = useState("");
  const { result, error, isLoading, run } = useAsync<PastThinkingResponse>();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic || !at) return;
    run(() => pastThinking(topic, new Date(at).toISOString()));
  }

  return (
    <div>
      <form onSubmit={submit} aria-labelledby={headingId} className="flex flex-col gap-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <Field id="past-topic" label="Tema">
            <input
              id="past-topic"
              type="text"
              required
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Por ejemplo, trabajo"
              enterKeyHint="next"
              className={INPUT_CLASS}
            />
          </Field>
          <Field id="past-at" label="Fecha y hora">
            <input
              id="past-at"
              type="datetime-local"
              required
              value={at}
              onChange={(e) => setAt(e.target.value)}
              enterKeyHint="search"
              className={INPUT_CLASS}
            />
          </Field>
          <Button type="submit" disabled={isLoading || !topic || !at}>
            {isLoading ? "Consultando…" : "Preguntar"}
          </Button>
        </div>
      </form>
      <QueryError message={error} />
      <QueryStatus loading={isLoading} />
      {!isLoading && result && (
        result.items.length === 0 ? (
          <div className="mt-6">
            <EmptyState
              title="No hay recuerdos de ese momento."
              action={
                <Button type="button" variant="ghost" onClick={() => document.getElementById("past-topic")?.focus()}>
                  Probar otra fecha
                </Button>
              }
            >
              Cambia el tema o elige otra fecha.
            </EmptyState>
          </div>
        ) : (
          <ul className="mt-6 space-y-3">
            {result.items.map((item) => (
              <Card as="li" key={`${item.node_id}-${item.version}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <ObjectTypeBadge objectType={item.object_type} />
                  <span className="text-body-sm font-medium text-obsidian">{item.title}</span>
                </div>
                <p className="mt-2 line-clamp-3 text-body-sm text-slate">{item.content}</p>
                <p className="mt-2 font-mono text-mono-sm text-muted">similitud {item.similarity.toFixed(2)}</p>
              </Card>
            ))}
          </ul>
        )
      )}
    </div>
  );
}

function SimilarIdeasWidget({ headingId }: { headingId: string }) {
  const [nodeId, setNodeId] = useState("");
  const { result, error, isLoading, run } = useAsync<SimilarIdeasResponse>();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!nodeId) return;
    run(() => similarIdeas(nodeId));
  }

  return (
    <div>
      <form onSubmit={submit} aria-labelledby={headingId} className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <Field id="similar-node" label="Identificador del recuerdo">
          <input
            id="similar-node"
            type="text"
            required
            value={nodeId}
            onChange={(e) => setNodeId(e.target.value)}
            placeholder="Cópialo desde Búsqueda"
            spellCheck={false}
            autoCapitalize="off"
            enterKeyHint="search"
            className={`${INPUT_CLASS} font-mono text-mono`}
          />
        </Field>
        <Button type="submit" disabled={isLoading || !nodeId}>
          {isLoading ? "Consultando…" : "Preguntar"}
        </Button>
      </form>
      <QueryError message={error} />
      <QueryStatus loading={isLoading} />
      {!isLoading && result && (
        result.items.length === 0 ? (
          <div className="mt-6">
            <EmptyState
              title="No hay ideas parecidas."
              action={
                <Button type="button" variant="ghost" onClick={() => document.getElementById("similar-node")?.focus()}>
                  Probar otro identificador
                </Button>
              }
            >
              Prueba con otro recuerdo, copiado desde Búsqueda.
            </EmptyState>
          </div>
        ) : (
          <ul className="mt-6 space-y-3">
            {result.items.map((item) => (
              <Card as="li" key={item.node_id}>
                <div className="flex flex-wrap items-center gap-2">
                  <ObjectTypeBadge objectType={item.object_type} />
                  <span className="text-body-sm font-medium text-obsidian">{item.title}</span>
                </div>
                <p className="mt-2 font-mono text-mono-sm text-muted">similitud {item.similarity.toFixed(2)}</p>
              </Card>
            ))}
          </ul>
        )
      )}
    </div>
  );
}

function DecisionsWidget({ headingId }: { headingId: string }) {
  const [topic, setTopic] = useState("");
  const { result, error, isLoading, run } = useAsync<DecisionsResponse>();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic) return;
    run(() => decisions(topic));
  }

  return (
    <div>
      <form onSubmit={submit} aria-labelledby={headingId} className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <Field id="decisions-topic" label="Tema">
          <input
            id="decisions-topic"
            type="text"
            required
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Por ejemplo, mudanza"
            enterKeyHint="search"
            className={INPUT_CLASS}
          />
        </Field>
        <Button type="submit" disabled={isLoading || !topic}>
          {isLoading ? "Consultando…" : "Preguntar"}
        </Button>
      </form>
      <QueryError message={error} />
      <QueryStatus loading={isLoading} />
      {!isLoading && result && (
        result.decisions.length === 0 ? (
          <div className="mt-6">
            <EmptyState
              title="No hay decisiones sobre ese tema."
              action={
                <Button type="button" variant="ghost" onClick={() => document.getElementById("decisions-topic")?.focus()}>
                  Probar otro tema
                </Button>
              }
            >
              Prueba con otras palabras.
            </EmptyState>
          </div>
        ) : (
          <ul className="mt-6 space-y-3">
            {result.decisions.map((d) => (
              <Card as="li" key={d.node_id}>
                <p className="text-body-sm font-medium text-obsidian">{d.title}</p>
                {d.rationale && <p className="mt-2 text-body-sm text-slate">{d.rationale}</p>}
                <p className="mt-2 font-mono text-mono-sm text-muted">{new Date(d.created_at).toLocaleString("es")}</p>
              </Card>
            ))}
          </ul>
        )
      )}
    </div>
  );
}

function SupportWidget({ headingId }: { headingId: string }) {
  const [nodeId, setNodeId] = useState("");
  const { result, error, isLoading, run } = useAsync<SupportResponse>();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!nodeId) return;
    run(() => support(nodeId));
  }

  return (
    <div>
      <form onSubmit={submit} aria-labelledby={headingId} className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <Field id="support-node" label="Identificador del recuerdo">
          <input
            id="support-node"
            type="text"
            required
            value={nodeId}
            onChange={(e) => setNodeId(e.target.value)}
            placeholder="Cópialo desde Búsqueda"
            spellCheck={false}
            autoCapitalize="off"
            enterKeyHint="search"
            className={`${INPUT_CLASS} font-mono text-mono`}
          />
        </Field>
        <Button type="submit" disabled={isLoading || !nodeId}>
          {isLoading ? "Consultando…" : "Preguntar"}
        </Button>
      </form>
      <QueryError message={error} />
      <QueryStatus loading={isLoading} />
      {!isLoading && result && (
        result.support.length === 0 ? (
          <div className="mt-6">
            <EmptyState
              title="No hay respaldo registrado."
              action={
                <Button type="button" variant="ghost" onClick={() => document.getElementById("support-node")?.focus()}>
                  Probar otro identificador
                </Button>
              }
            >
              Este recuerdo no tiene notas que lo sostengan. Prueba con otro.
            </EmptyState>
          </div>
        ) : (
          <ul className="mt-6 space-y-2">
            {result.support.map((ev, i) => (
              <EvidenceTree key={`${ev.node_id}-${i}`} evidence={ev} depth={0} />
            ))}
          </ul>
        )
      )}
    </div>
  );
}

function ContradictionsWidget({ headingId }: { headingId: string }) {
  const [topic, setTopic] = useState("");
  const { result, error, isLoading, run } = useAsync<ContradictionsResponse>();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic) return;
    run(() => contradictionsByTopic(topic));
  }

  return (
    <div>
      <form onSubmit={submit} aria-labelledby={headingId} className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <Field id="cog-contradiction-topic" label="Tema">
          <input
            id="cog-contradiction-topic"
            type="text"
            required
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Por ejemplo, salud"
            enterKeyHint="search"
            className={INPUT_CLASS}
          />
        </Field>
        <Button type="submit" disabled={isLoading || !topic}>
          {isLoading ? "Consultando…" : "Preguntar"}
        </Button>
      </form>
      <QueryError message={error} />
      <QueryStatus loading={isLoading} />
      {!isLoading && result && (
        result.contradictions.length === 0 ? (
          <div className="mt-6">
            <EmptyState
              title="No hay contradicciones para este tema."
              action={
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => document.getElementById("cog-contradiction-topic")?.focus()}
                >
                  Probar otro tema
                </Button>
              }
            >
              Prueba con otras palabras.
            </EmptyState>
          </div>
        ) : (
          <ul className="mt-6 space-y-4">
            {result.contradictions.map((pair) => (
              <ContradictionCard key={`${pair.node_a_id}-${pair.node_b_id}`} pair={pair} />
            ))}
          </ul>
        )
      )}
    </div>
  );
}

function PatternsWidget({ headingId }: { headingId: string }) {
  const { result, error, isLoading, run } = useAsync<PatternsResponse>();
  const captionId = "patterns-caption";

  function submit(e: React.FormEvent) {
    e.preventDefault();
    run(() => patterns());
  }

  return (
    <div>
      <form onSubmit={submit} aria-labelledby={headingId}>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Analizando…" : "Analizar"}
        </Button>
      </form>
      <QueryError message={error} />
      <QueryStatus loading={isLoading} />
      {!isLoading && result && (
        <div className="mt-6">
          <p className="text-body-sm text-slate">
            {formatNumber(result.total_nodes)} recuerdos analizados.
            {result.most_common_type ? " El tipo más común es " : " Sin un tipo dominante."}
            {result.most_common_type && <ObjectTypeBadge objectType={result.most_common_type} />}
          </p>
          {result.buckets.length === 0 ? (
            <div className="mt-4">
              <EmptyState
                title="Todavía no hay un patrón visible."
                action={
                  <Button type="button" variant="ghost" onClick={() => run(() => patterns())}>
                    Volver a analizar
                  </Button>
                }
              >
                Hace falta más memoria guardada para comparar periodos.
              </EmptyState>
            </div>
          ) : (
            <div role="region" aria-labelledby={captionId} tabIndex={0} className="mt-4 max-w-full overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <caption id={captionId} className="sr-only">
                  Patrones por periodo
                </caption>
                <thead>
                  <tr>
                    <th scope="col" className="border-b border-obsidian py-2 pr-4 text-left">
                      <MonoLabel>Periodo</MonoLabel>
                    </th>
                    <th scope="col" className="border-b border-obsidian py-2 pr-4 text-left">
                      <MonoLabel>Tipo</MonoLabel>
                    </th>
                    <th scope="col" className="border-b border-obsidian py-2 text-left">
                      <MonoLabel>Cantidad</MonoLabel>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {result.buckets.map((b, i) => (
                    <tr key={`${b.period}-${b.object_type}-${i}`}>
                      <th scope="row" className="border-b border-hairline py-2 pr-4 text-body-sm font-normal text-obsidian">
                        {b.period}
                      </th>
                      <td className="border-b border-hairline py-2 pr-4">
                        <ObjectTypeBadge objectType={b.object_type} />
                      </td>
                      <td className="border-b border-hairline py-2 text-body-sm tabular-nums text-obsidian">
                        {formatNumber(b.count)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ConclusionNote() {
  return (
    <Card>
      <p className="max-w-[40rem] text-body-sm text-slate">
        Esa respuesta está en Razonamiento. Pega el identificador de un recuerdo y verás la evidencia, paso a paso.
      </p>
      <div className="mt-5">
        <ButtonLink href="/explain">Ir a razonamiento</ButtonLink>
      </div>
    </Card>
  );
}

function QuestionTabs({ active, onChange }: { active: QuestionId; onChange: (id: QuestionId) => void }) {
  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
    const current = tabs.indexOf(event.target as HTMLButtonElement);
    if (current < 0) return;
    const last = tabs.length - 1;
    let next = current;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = current === last ? 0 : current + 1;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = current === 0 ? last : current - 1;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = last;
    else return;
    event.preventDefault();
    const id = tabs[next].dataset.question;
    if (!id) return;
    onChange(id as QuestionId);
    tabs[next].focus();
  }

  return (
    <div
      role="tablist"
      aria-label="Siete preguntas"
      onKeyDown={onKeyDown}
      className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4"
    >
      {QUESTIONS.map((tab) => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            type="button"
            role="tab"
            data-question={tab.id}
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className="relative min-w-0 rounded-md border border-hairline bg-paper px-4 pt-5 pb-7 text-center text-subheading font-medium wrap-anywhere text-slate hover:text-obsidian aria-selected:border-transparent aria-selected:bg-mint aria-selected:text-obsidian"
          >
            {tab.label}
            <span
              aria-hidden="true"
              className={`absolute inset-x-4 bottom-3 border-b-2 ${selected ? "border-periwinkle" : "border-transparent"}`}
            />
          </button>
        );
      })}
    </div>
  );
}

function QuestionPanel({
  active,
  labelledBy,
  onSelect,
  children,
}: {
  active: boolean;
  labelledBy: string;
  onSelect: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // React 19 escribe `hidden` como booleano y descarta "until-found".
    const panel: { hidden: boolean | string } = el;
    panel.hidden = active ? false : "until-found";
    const onBeforeMatch = () => onSelect();
    el.addEventListener("beforematch", onBeforeMatch);
    return () => el.removeEventListener("beforematch", onBeforeMatch);
  }, [active, onSelect]);

  return (
    <div ref={ref} role="tabpanel" aria-labelledby={labelledBy} hidden={!active}>
      {children}
    </div>
  );
}

function QuestionBody({ id, headingId }: { id: QuestionId; headingId: string }) {
  switch (id) {
    case "fecha":
      return <PastThinkingWidget headingId={headingId} />;
    case "similares":
      return <SimilarIdeasWidget headingId={headingId} />;
    case "decisiones":
      return <DecisionsWidget headingId={headingId} />;
    case "respaldo":
      return <SupportWidget headingId={headingId} />;
    case "contradicciones":
      return <ContradictionsWidget headingId={headingId} />;
    case "patrones":
      return <PatternsWidget headingId={headingId} />;
    case "conclusion":
      return <ConclusionNote />;
  }
}

export default function CognitivePage() {
  const [active, setActive] = useState<QuestionId>("fecha");

  return (
    <div>
      <PageHeader
        title="Siete preguntas"
        continuation="que tu memoria sabe responder"
        description="Elige una pregunta y consulta lo que ya guardaste."
      />
      {/* Una columna hasta sm: TabCards fuerza dos columnas de 22 px y "Contradicciones" se sale a 375 px. */}
      <QuestionTabs active={active} onChange={setActive} />
      {QUESTIONS.map((question) => (
        <QuestionPanel
          key={question.id}
          active={active === question.id}
          labelledBy={`tab-${question.id}`}
          onSelect={() => setActive(question.id)}
        >
          <div className="mt-12">
            <div id={`heading-${question.id}`}>
              <SectionTitle>{question.question}</SectionTitle>
            </div>
            <QuestionBody id={question.id} headingId={`heading-${question.id}`} />
          </div>
        </QuestionPanel>
      ))}
    </div>
  );
}
