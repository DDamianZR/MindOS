"use client";

import { useEffect, useId, useRef, useState } from "react";

import { BarList, ColumnChart, type ChartPoint } from "@/components/charts";
import { HeroGraphic } from "@/components/HeroGraphic";
import {
  Button,
  ButtonLink,
  Card,
  Container,
  DarkBand,
  EmptyState,
  ErrorNotice,
  PageHeader,
  PaperCard,
  SectionTitle,
  Skeleton,
  StatCard,
  formatNumber,
  formatUsd,
} from "@/components/ui";
import {
  type AssistantStatsResponse,
  type CountItem,
  type MemoryStatsResponse,
  type RecentNode,
  getAssistantStats,
  getMemoryStats,
} from "@/lib/stats-client";

// Mismo mapa que el margen del asistente: el tipo se lee en español en toda la portada.
const TYPE_LABELS: Record<string, string> = {
  note: "nota", idea: "idea", document: "documento", conversation: "conversación",
  concept: "concepto", person: "persona", project: "proyecto", task: "tarea",
  resource: "recurso", technology: "tecnología", event: "evento", observation: "observación",
  experience: "experiencia", question: "pregunta", hypothesis: "hipótesis",
  investigation: "investigación", evidence: "evidencia", decision: "decisión",
  outcome: "resultado", learning: "aprendizaje", fact: "hecho", insight: "hallazgo",
};

const SOURCE_LABELS: Record<string, string> = {
  whatsapp: "whatsapp",
  pdf: "pdf",
  image: "imagen",
  audio: "audio",
  web: "web",
  cli: "cli",
  api: "api",
  agent: "agente",
};

const TOOL_LABELS: Record<string, string> = {
  search_memory: "Buscar en la memoria",
  save_memory: "Guardar",
  list_decisions: "Decisiones",
  find_contradictions: "Contradicciones",
  recall_past_thinking: "Pensamiento pasado",
  explain_knowledge: "Explicar",
  get_history: "Historial",
  web_search: "Buscar en la web",
  web_fetch: "Leer una página",
  create_routine: "Proponer rutina",
  list_routines: "Ver rutinas",
};

type Load<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

const MEMORY_ERROR = "No se pudieron cargar las cifras de tu memoria. Comprueba la conexión e inténtalo de nuevo.";
const AGENT_ERROR = "No se pudieron cargar las cifras del asistente. Comprueba la conexión e inténtalo de nuevo.";

/** Los días del API son fechas UTC (YYYY-MM-DD). Tratarlas como UTC evita que el día cambie de zona. */
const DAY_FORMAT = new Intl.DateTimeFormat("es", { day: "numeric", month: "short", timeZone: "UTC" });
const WHEN_FORMAT = new Intl.DateTimeFormat("es", { day: "numeric", month: "short", year: "numeric" });
const PERCENT_FORMAT = new Intl.NumberFormat("es", { style: "percent", maximumFractionDigits: 0 });

function labelFor(key: string, labels: Record<string, string>): string {
  return labels[key] ?? labels[key.toLowerCase()] ?? key;
}

function pointsFrom(items: CountItem[] | undefined, labels: Record<string, string>): ChartPoint[] {
  return (items ?? []).map((item) => ({ label: labelFor(item.key, labels), value: item.count }));
}

function utcDay(iso: string): Date {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(year || 1970, (month || 1) - 1, day || 1));
}

function formatDay(iso: string): string {
  return DAY_FORMAT.format(utcDay(iso));
}

function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return WHEN_FORMAT.format(date);
}

function countPhrase(count: number, singular: string, plural: string): string {
  return `${formatNumber(count)} ${count === 1 ? singular : plural}`;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || Number.isNaN(seconds)) return "sin datos";
  if (seconds < 60) {
    const digits = seconds < 10 ? 1 : 0;
    const text = new Intl.NumberFormat("es", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(seconds);
    return `${text} s`;
  }
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  if (rest === 0) return `${formatNumber(minutes)} min`;
  return `${formatNumber(minutes)} min ${rest} s`;
}

function formatCache(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return "sin datos";
  return PERCENT_FORMAT.format(ratio);
}

function activityLine(activeDays: number): string {
  if (activeDays === 0) return "Ningún día tuvo actividad.";
  if (activeDays === 1) return "1 día tuvo actividad.";
  return `${formatNumber(activeDays)} días tuvieron actividad.`;
}

function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function slideOffset(track: HTMLElement, slide: HTMLElement): number {
  // getBoundingClientRect sigue siendo válido si algún ancestro está posicionado.
  return slide.getBoundingClientRect().left - track.getBoundingClientRect().left + track.scrollLeft;
}

function nearestSlide(track: HTMLElement, slides: HTMLElement[]): number {
  const origin = track.scrollLeft;
  let best = 0;
  let bestDistance = Number.POSITIVE_INFINITY;
  slides.forEach((slide, index) => {
    const distance = Math.abs(slideOffset(track, slide) - origin);
    if (distance < bestDistance) {
      best = index;
      bestDistance = distance;
    }
  });
  return best;
}

function RecentStrip({ nodes }: { nodes: RecentNode[] }) {
  const trackId = useId();
  const trackRef = useRef<HTMLDivElement>(null);
  const prevRef = useRef<HTMLButtonElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const pending = useRef<number | null>(null);
  const userMoved = useRef(false);
  const lastAnnounced = useRef<number | null>(null);
  const [ends, setEnds] = useState({ atStart: true, atEnd: true });
  const [status, setStatus] = useState("");

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    const slides = () => [...track.querySelectorAll<HTMLElement>("[data-slide]")];

    const sync = (announce: boolean) => {
      const items = slides();
      if (items.length === 0) return;
      const index = pending.current ?? nearestSlide(track, items);
      const maxScroll = track.scrollWidth - track.clientWidth;
      const atStart = track.scrollLeft <= 1;
      const atEnd = maxScroll <= 1 || track.scrollLeft >= maxScroll - 1;
      setEnds({ atStart, atEnd });

      const prev = prevRef.current;
      const next = nextRef.current;
      if (document.activeElement === prev && atStart) {
        if (!atEnd) next?.focus();
        else items[0]?.querySelector("a")?.focus();
      } else if (document.activeElement === next && atEnd) {
        if (!atStart) prev?.focus();
        else items[0]?.querySelector("a")?.focus();
      }

      if (announce && lastAnnounced.current !== index) {
        lastAnnounced.current = index;
        setStatus(`Tarjeta ${index + 1} de ${items.length}`);
      }
    };

    sync(false);

    let timer = 0;
    const settle = () => {
      const items = slides();
      const target = pending.current === null ? null : items[pending.current];
      // Un scrollend viejo llega si el usuario pulsó otra vez antes de terminar: no pisa el destino nuevo.
      if (target && Math.abs(slideOffset(track, target) - track.scrollLeft) > 2) return;
      pending.current = null;
      sync(userMoved.current);
      userMoved.current = false;
    };
    const markUser = () => {
      userMoved.current = true;
    };
    // `in window` estrecha el tipo a never cuando el DOM ya declara onscrollend.
    const supportsScrollEnd = Object.prototype.hasOwnProperty.call(window, "onscrollend")
      || "onscrollend" in Window.prototype;
    const onScroll = () => {
      if (supportsScrollEnd) return;
      clearTimeout(timer);
      timer = window.setTimeout(settle, 140);
    };

    track.addEventListener("scroll", onScroll, { passive: true });
    track.addEventListener("wheel", markUser, { passive: true });
    track.addEventListener("pointerdown", markUser);
    track.addEventListener("keydown", markUser);
    if ("onscrollend" in window) track.addEventListener("scrollend", settle);
    const observer = new ResizeObserver(() => sync(false));
    observer.observe(track);

    return () => {
      window.clearTimeout(timer);
      track.removeEventListener("scroll", onScroll);
      track.removeEventListener("wheel", markUser);
      track.removeEventListener("pointerdown", markUser);
      track.removeEventListener("keydown", markUser);
      track.removeEventListener("scrollend", settle);
      observer.disconnect();
    };
  }, [nodes]);

  function step(direction: -1 | 1) {
    const track = trackRef.current;
    if (!track) return;
    const slides = [...track.querySelectorAll<HTMLElement>("[data-slide]")];
    if (slides.length === 0) return;
    const base = pending.current ?? nearestSlide(track, slides);
    const target = Math.min(slides.length - 1, Math.max(0, base + direction));
    const left = slideOffset(track, slides[target]);
    pending.current = target;
    userMoved.current = true;
    if (Math.abs(left - track.scrollLeft) < 1) {
      pending.current = null;
      return;
    }
    track.scrollTo({ left, behavior: prefersReducedMotion() ? "auto" : "smooth" });
  }

  return (
    <div role="region" aria-roledescription="carrusel" aria-label="Pensamiento reciente">
      <div className="relative">
        <SectionTitle dark>Pensamiento reciente</SectionTitle>
        <div className="mb-5 flex justify-end gap-2 sm:absolute sm:top-0 sm:right-0 sm:mb-0">
          <Button
            ref={prevRef}
            type="button"
            variant="ghost-dark"
            className="touch-manipulation"
            aria-controls={trackId}
            disabled={ends.atStart}
            onClick={() => step(-1)}
          >
            Anterior
          </Button>
          <Button
            ref={nextRef}
            type="button"
            variant="ghost-dark"
            className="touch-manipulation"
            aria-controls={trackId}
            disabled={ends.atEnd}
            onClick={() => step(1)}
          >
            Siguiente
          </Button>
        </div>
      </div>
      <div
        id={trackId}
        ref={trackRef}
        tabIndex={-1}
        className="flex w-full min-w-0 touch-manipulation snap-x snap-mandatory gap-4 overflow-x-auto overscroll-x-contain scroll-px-1 py-1 motion-safe:scroll-smooth"
        aria-label="Tarjetas"
      >
        {nodes.map((node, index) => (
          <div
            key={node.node_id}
            data-slide
            role="group"
            aria-roledescription="tarjeta"
            aria-label={`${node.title || "Sin título"}, ${index + 1} de ${nodes.length}`}
            className="w-[min(280px,78%)] shrink-0 snap-start"
          >
            <PaperCard
              href={`/explain?node_id=${node.node_id}`}
              badge={node.object_type ? labelFor(node.object_type, TYPE_LABELS) : "sin tipo"}
              title={node.title.trim() || "Sin título"}
              meta={formatWhen(node.created_at)}
            />
          </div>
        ))}
      </div>
      <p className="sr-only" role="status" aria-live="polite">
        {status}
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="mono-label text-slate">{label}</dt>
      <dd className="mt-1 text-subheading font-medium break-words text-obsidian tabular-nums">{value}</dd>
    </div>
  );
}

function MemoryStats({ memory }: { memory: Load<MemoryStatsResponse> }) {
  if (memory.status === "loading") {
    return (
      <>
        <Skeleton className="min-h-[180px]" />
        <Skeleton className="min-h-[180px]" />
      </>
    );
  }
  if (memory.status === "error") {
    return (
      <div className="sm:col-span-2">
        <ErrorNotice>{memory.message}</ErrorNotice>
      </div>
    );
  }
  const data = memory.data;
  return (
    <>
      <StatCard
        tone="memoria"
        label="NODOS EN TU MEMORIA"
        value={formatNumber(data.nodes)}
        caption={`en ${countPhrase(data.versions, "versión", "versiones")}`}
      />
      <StatCard
        tone="pensamiento"
        label="CONTRADICCIONES"
        value={formatNumber(data.contradictions)}
        caption={`entre ${countPhrase(data.relations, "relación", "relaciones")}`}
      />
    </>
  );
}

function ActivityStat({ memory }: { memory: Load<MemoryStatsResponse> }) {
  if (memory.status === "loading") return <Skeleton className="min-h-[180px]" />;
  if (memory.status === "error") return null;
  const created = (memory.data.activity ?? []).reduce((sum, day) => sum + day.created, 0);
  const updated = (memory.data.activity ?? []).reduce((sum, day) => sum + day.updated, 0);
  return (
    <StatCard
      tone="actividad"
      trend="up"
      label="NUEVOS EN 30 DÍAS"
      value={formatNumber(created)}
      caption={`y ${countPhrase(updated, "actualización", "actualizaciones")}`}
    />
  );
}

function AgentStat({ agent }: { agent: Load<AssistantStatsResponse> }) {
  if (agent.status === "loading") return <Skeleton className="min-h-[180px]" />;
  if (agent.status === "error") return <ErrorNotice>{agent.message}</ErrorNotice>;
  const data = agent.data;
  return (
    <StatCard
      tone="agente"
      label="TURNOS DEL ASISTENTE"
      value={formatNumber(data.turns)}
      caption={data.provider === "demo" ? "en modo demostración" : `costo estimado ${formatUsd(data.estimated_cost_usd)}`}
    />
  );
}

export default function InicioPage() {
  const [memory, setMemory] = useState<Load<MemoryStatsResponse>>({ status: "loading" });
  const [agent, setAgent] = useState<Load<AssistantStatsResponse>>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    getMemoryStats()
      .then((data) => {
        if (!cancelled) setMemory({ status: "ready", data });
      })
      .catch(() => {
        if (!cancelled) setMemory({ status: "error", message: MEMORY_ERROR });
      });
    getAssistantStats()
      .then((data) => {
        if (!cancelled) setAgent({ status: "ready", data });
      })
      .catch(() => {
        if (!cancelled) setAgent({ status: "error", message: AGENT_ERROR });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const memoryReady = memory.status === "ready" ? memory.data : null;
  const emptyMemory = memoryReady !== null && memoryReady.nodes === 0;

  return (
    <div className="overflow-x-clip pb-0">
      <section className="pt-12 md:pt-16">
        <Container>
          <div className="grid items-center gap-10 md:grid-cols-2 md:gap-12">
            <div className="min-w-0">
              <PageHeader
                size="display"
                title="Todo lo que sabes,"
                continuation="con su porqué y su fecha."
                description="MindOS guarda lo que piensas, decides y capturas como un grafo con versiones y fuentes. Su agente lo consulta, detecta dónde te contradices y trabaja por ti cuando se lo pides."
                actions={
                  <>
                    <ButtonLink href="/assistant">Preguntar</ButtonLink>
                    <ButtonLink href="/capture" variant="ghost">
                      Capturar algo
                    </ButtonLink>
                  </>
                }
              />
            </div>
            <HeroGraphic className="h-52 w-full min-w-0 md:h-[420px]" />
          </div>
        </Container>
      </section>

      <section className="mt-16 md:mt-20">
        <Container>
          <h2 className="sr-only">Cifras</h2>
          {memory.status === "loading" && <p className="sr-only">Cargando las cifras de tu memoria.</p>}
          {agent.status === "loading" && <p className="sr-only">Cargando las cifras del asistente.</p>}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MemoryStats memory={memory} />
            <AgentStat agent={agent} />
            <ActivityStat memory={memory} />
          </div>
        </Container>
      </section>

      {emptyMemory ? (
        <section className="mt-16 md:mt-20">
          <Container>
            <EmptyState
              title="Tu memoria está vacía"
              action={<ButtonLink href="/capture">Capturar la primera nota</ButtonLink>}
            >
              Cuando guardes la primera nota, aquí verás de qué está hecha y cómo cambia.
            </EmptyState>
          </Container>
        </section>
      ) : (
        <>
          <section className="mt-16 md:mt-20">
            <Container>
              <SectionTitle>Qué hay en tu memoria</SectionTitle>
              {memory.status === "loading" && (
                <div className="grid gap-4 md:grid-cols-2">
                  <Skeleton className="h-64" />
                  <Skeleton className="h-64" />
                </div>
              )}
              {memory.status === "error" && <ErrorNotice>{memory.message}</ErrorNotice>}
              {memoryReady && (
                <div className="grid gap-4 md:grid-cols-2">
                  <Card className="min-w-0">
                    <h3 className="mono-label mb-4 text-slate">Por tipo</h3>
                    <BarList
                      label="Nodos por tipo"
                      categoryLabel="Tipo"
                      points={pointsFrom(memoryReady.by_type, TYPE_LABELS)}
                    />
                  </Card>
                  <Card className="min-w-0">
                    <h3 className="mono-label mb-4 text-slate">Por origen</h3>
                    <BarList
                      label="Nodos por origen"
                      categoryLabel="Origen"
                      points={pointsFrom(memoryReady.by_source, SOURCE_LABELS)}
                    />
                  </Card>
                </div>
              )}
            </Container>
          </section>

          <section className="mt-16 md:mt-20">
            <Container>
              <SectionTitle>Actividad de los últimos 30 días</SectionTitle>
              {memory.status === "loading" && <Skeleton className="h-56" />}
              {memory.status === "error" && <ErrorNotice>{memory.message}</ErrorNotice>}
              {memoryReady && (
                <ColumnChart
                  label="Actividad de los últimos 30 días"
                  categoryLabel="Día"
                  valueLabel="Cambios"
                  points={(memoryReady.activity ?? []).map((day) => ({
                    label: formatDay(day.date),
                    value: day.created + day.updated,
                  }))}
                  note={activityLine(
                    (memoryReady.activity ?? []).filter((day) => day.created + day.updated > 0).length,
                  )}
                />
              )}
            </Container>
          </section>
        </>
      )}

      <section className="mt-16 md:mt-20">
        <Container>
          <SectionTitle>El agente</SectionTitle>
          {agent.status === "loading" && <Skeleton className="h-80" />}
          {agent.status === "error" && <ErrorNotice>{agent.message}</ErrorNotice>}
          {agent.status === "ready" && <AgentPanel stats={agent.data} />}
        </Container>
      </section>

      <DarkBand className="mt-16 md:mt-20">
        {memory.status === "ready" && memory.data.recent_thinking.length > 0 ? (
          <RecentStrip nodes={memory.data.recent_thinking} />
        ) : (
          <>
            <SectionTitle dark>Pensamiento reciente</SectionTitle>
            {memory.status === "loading" && (
              <>
                <p className="sr-only">Cargando el pensamiento reciente.</p>
                <div className="flex gap-4 overflow-hidden">
                  <Skeleton className="h-48 w-72 shrink-0" />
                  <Skeleton className="h-48 w-72 shrink-0" />
                  <Skeleton className="hidden h-48 w-72 shrink-0 sm:block" />
                </div>
              </>
            )}
            {memory.status === "error" && <ErrorNotice>{memory.message}</ErrorNotice>}
            {memoryReady && memoryReady.recent_thinking.length === 0 && (
              <div>
                <p className="max-w-[36rem] text-body-sm text-paper/70">
                  Aún no hay decisiones ni aprendizajes registrados. Aparecen aquí cuando los guardas o el agente los produce.
                </p>
                <div className="mt-5">
                  <ButtonLink href="/assistant" variant="ghost-dark">
                    Preguntar
                  </ButtonLink>
                </div>
              </div>
            )}
          </>
        )}
      </DarkBand>
    </div>
  );
}

function AgentPanel({ stats }: { stats: AssistantStatsResponse }) {
  const turns = (stats.turns_by_day ?? []).map((day) => ({
    label: formatDay(day.date),
    value: day.turns,
  }));
  const tools = pointsFrom(stats.tool_calls, TOOL_LABELS);
  const usage = stats.usage ?? {
    input_tokens: 0,
    output_tokens: 0,
    cache_read_input_tokens: 0,
    cache_creation_input_tokens: 0,
  };

  return (
    <Card className="min-w-0">
      <div className="grid gap-10 lg:grid-cols-2">
        <div className="min-w-0">
          <h3 className="mono-label mb-4 text-slate">Turnos por día</h3>
          <ColumnChart label="Turnos del asistente por día" categoryLabel="Día" valueLabel="Turnos" points={turns} />
        </div>
        <dl className="grid content-start grid-cols-2 gap-x-4 gap-y-6">
          <Metric label="Tokens de entrada" value={formatNumber(usage.input_tokens)} />
          <Metric label="Tokens de salida" value={formatNumber(usage.output_tokens)} />
          <Metric label="Aciertos de caché" value={formatCache(stats.cache_hit_ratio)} />
          <Metric label="Duración media de un turno" value={formatDuration(stats.avg_turn_seconds)} />
          <Metric label="Turnos fallidos" value={formatNumber(stats.failed_turns)} />
        </dl>
      </div>
      <div className="mt-10">
        <h3 className="mono-label mb-4 text-slate">Herramientas</h3>
        <BarList
          label="Herramientas que usó el asistente"
          categoryLabel="Herramienta"
          valueLabel="Usos"
          emptyText="Todavía no ha usado herramientas."
          points={tools}
        />
      </div>
      <p className="mt-4 text-caption text-slate">Desde que arrancó el servicio de agentes.</p>
    </Card>
  );
}
