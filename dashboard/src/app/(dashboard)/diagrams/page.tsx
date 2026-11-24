"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useId, useRef, useState, type MouseEvent } from "react";

import { DiagramViewer, StatusMark, statusLabel } from "@/components/diagrams/DiagramViewer";
import { MermaidDiagram, type MermaidResult } from "@/components/diagrams/MermaidDiagram";
import { ButtonLink, EmptyState, MonoLabel, PageHeader, Skeleton, formatNumber } from "@/components/ui";
import { DIAGRAM_CATEGORIES, type Diagram } from "@/content/diagrams";

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

function diagramHref(id: string): string {
  const params = new URLSearchParams();
  params.set("d", id);
  return `/diagrams?${params.toString()}`;
}

function DiagramsHeader() {
  return (
    <PageHeader
      title="Diagramas"
      continuation="cómo está hecho MindOS"
      description="El catálogo completo de diagramas del sistema, dibujados a partir del código. Los que no describen nada que MindOS tenga hoy están marcados con el motivo."
      actions={
        <ButtonLink href="https://ddamianzr.github.io/MindOS/" variant="ghost" target="_blank" rel="noreferrer">
          C4 interactivo
        </ButtonLink>
      }
    />
  );
}

function CatalogCounts({ diagrams }: { diagrams: Diagram[] }) {
  const generated = diagrams.filter((diagram) => diagram.status === "generated").length;
  const existing = diagrams.filter((diagram) => diagram.status === "existing").length;
  const skipped = diagrams.filter((diagram) => diagram.status === "not_applicable").length;
  const items = [
    { label: "Generados", value: generated },
    { label: "Existentes", value: existing },
    { label: "No aplican", value: skipped },
  ];
  return (
    <dl className="mt-12 grid grid-cols-3 gap-3">
      {items.map((item) => (
        <div key={item.label} className="min-w-0">
          <dt>
            <MonoLabel>{item.label}</MonoLabel>
          </dt>
          <dd className="mt-1 text-heading-sm font-medium text-obsidian tabular-nums">{formatNumber(item.value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function DiagramsFallback() {
  return (
    <div>
      <p className="sr-only">Cargando los diagramas.</p>
      <Skeleton className="h-24 w-full max-w-xl" />
      <div className="mt-12 grid grid-cols-3 gap-3">
        <Skeleton className="h-16" />
        <Skeleton className="h-16" />
        <Skeleton className="h-16" />
      </div>
      <Skeleton className="mt-16 h-80 w-full" />
    </div>
  );
}

interface ReviewRow {
  id: string;
  title: string;
  ok: boolean;
  message?: string;
}

function Verification({ diagrams }: { diagrams: Diagram[] }) {
  const [cursor, setCursor] = useState(0);
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const seen = useRef(new Set<string>());
  const current = diagrams[cursor];
  const total = diagrams.length;
  const position = total === 0 ? 0 : Math.min(cursor + (cursor < total ? 1 : 0), total);

  function settle(id: string, title: string, result: MermaidResult) {
    if (seen.current.has(id)) return;
    seen.current.add(id);
    setRows((prev) => [
      ...prev,
      { id, title, ok: result.ok, message: result.ok ? undefined : result.message },
    ]);
    setCursor((value) => value + 1);
  }

  if (total === 0) {
    return (
      <div className="mt-16">
        <EmptyState
          title="No hay diagramas generados para revisar."
          action={
            <ButtonLink href="/diagrams" variant="ghost">
              Volver al catálogo
            </ButtonLink>
          }
        >
          Ningún diagrama del catálogo está dibujado con código.
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="mt-16">
      <p className="max-w-[40rem] text-body text-slate">
        Se dibujan uno por uno los diagramas hechos con código, para comprobar que se pueden leer.
      </p>
      <p id="revision-progreso" className="mt-6 font-mono text-mono text-muted">
        {position} de {total}
      </p>
      <progress
        className="mt-3 block h-2 w-full max-w-xs accent-obsidian"
        max={total}
        value={cursor}
        aria-labelledby="revision-progreso"
      />
      {current ? (
        <p className="mt-3 text-caption text-slate">
          Revisando {current.id} {current.title}
        </p>
      ) : (
        <p className="mt-3 text-caption text-slate">Revisión terminada.</p>
      )}
      <div
        tabIndex={0}
        role="region"
        aria-labelledby="revision-caption"
        className="mt-8 max-w-full overflow-x-auto"
      >
        <table className="w-full border-collapse text-left">
          <caption id="revision-caption" className="mb-4 text-left text-body-sm font-medium text-obsidian">
            Resultado de la comprobación
          </caption>
          <thead className="sticky top-0 bg-paper">
            <tr className="border-b border-hairline">
              <th scope="col" className="py-2 pr-4 font-mono text-mono-sm font-medium">
                Id
              </th>
              <th scope="col" className="py-2 pr-4 text-caption font-medium">
                Título
              </th>
              <th scope="col" className="py-2 text-caption font-medium">
                Resultado
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-hairline align-top">
                <th scope="row" className="py-2 pr-4 font-mono text-mono font-medium text-obsidian">
                  {row.id}
                </th>
                <td className="py-2 pr-4 text-body-sm break-words text-obsidian">{row.title}</td>
                <td className={cx("py-2 text-caption break-words", row.ok ? "text-obsidian" : "text-danger")}>
                  {row.ok ? "Bien" : row.message}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/*
        Recorte de 0 px: el dibujo se mide a 800 px pero no ensancha la página.
        Uno por vez, para no congelar el navegador con todo el catálogo.
      */}
      <div inert className="pointer-events-none fixed top-0 left-0 h-0 w-0 overflow-hidden">
        <div className="w-[800px]">
          {current && (
            <MermaidDiagram
              key={current.id}
              code={current.mermaid ?? ""}
              label={current.title}
              quiet
              onSettled={(result) => settle(current.id, current.title, result)}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function DiagramsCatalog() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const selectId = useId();
  const diagrams = DIAGRAM_CATEGORIES.flatMap((category) => category.diagrams);
  const families = DIAGRAM_CATEGORIES.filter((category) => category.diagrams.length > 0);
  const verifying = searchParams.get("verificar") === "1";
  const requested = searchParams.get("d");
  const selected =
    diagrams.find((diagram) => diagram.id === requested) ??
    diagrams.find((diagram) => diagram.status !== "not_applicable") ??
    diagrams[0];

  function openDiagram(event: MouseEvent<HTMLAnchorElement>, id: string) {
    if (event.button !== 0 || event.metaKey || event.altKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    router.replace(diagramHref(id), { scroll: false });
  }

  if (diagrams.length === 0) {
    return (
      <>
        <DiagramsHeader />
        <div className="mt-16">
          <EmptyState
            title="El catálogo todavía no tiene diagramas."
            action={
              <ButtonLink href="https://ddamianzr.github.io/MindOS/" variant="ghost" target="_blank" rel="noreferrer">
                C4 interactivo
              </ButtonLink>
            }
          >
            Cuando cada familia tenga los suyos, vas a poder verlos desde aquí.
          </EmptyState>
        </div>
      </>
    );
  }

  const selectedIndex = selected ? diagrams.findIndex((diagram) => diagram.id === selected.id) : -1;
  const previous = selectedIndex > 0 ? diagrams[selectedIndex - 1] : undefined;
  const next = selectedIndex >= 0 && selectedIndex < diagrams.length - 1 ? diagrams[selectedIndex + 1] : undefined;

  return (
    <>
      <DiagramsHeader />
      <CatalogCounts diagrams={diagrams} />
      {verifying ? (
        <Verification diagrams={diagrams.filter((diagram) => diagram.status === "generated")} />
      ) : (
        selected && (
          <div className="mt-16 md:grid md:grid-cols-[260px_minmax(0,1fr)] md:items-start md:gap-10">
            <div className="md:hidden">
              <label htmlFor={selectId} className="mono-label">
                Diagrama
              </label>
              <select
                id={selectId}
                value={selected.id}
                onChange={(event) => router.replace(diagramHref(event.target.value), { scroll: false })}
                className="mt-2 w-full rounded-md border border-hairline bg-paper px-3 py-2 text-body-sm text-obsidian"
              >
                {families.map((category) => (
                  <optgroup key={category.id} label={category.title}>
                    {category.diagrams.map((diagram) => (
                      <option key={diagram.id} value={diagram.id}>
                        {diagram.id} {diagram.title} · {statusLabel(diagram.status)}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
            <div className="hidden md:block">
              <nav
                aria-label="Familias de diagramas"
                className="sticky top-20 max-h-[calc(100dvh-6rem)] overflow-y-auto"
              >
                <ol className="list-none space-y-6">
                  {families.map((category) => (
                    <li key={category.id}>
                      <p className="text-body-sm font-medium text-obsidian">{category.title}</p>
                      {category.summary && <p className="mt-1 text-caption text-slate">{category.summary}</p>}
                      <ol className="mt-2 list-none">
                        {category.diagrams.map((diagram) => {
                          const active = diagram.id === selected.id;
                          return (
                            <li key={diagram.id}>
                              <Link
                                href={diagramHref(diagram.id)}
                                scroll={false}
                                aria-current={active ? "true" : undefined}
                                onClick={(event) => openDiagram(event, diagram.id)}
                                className={cx(
                                  "flex items-start gap-2 py-1.5 text-body-sm",
                                  active ? "text-obsidian" : "text-slate hover:text-obsidian",
                                )}
                              >
                                <span className="w-10 shrink-0 font-mono text-mono text-muted tabular-nums">
                                  {diagram.id}
                                </span>
                                <span
                                  className={cx(
                                    "min-w-0 flex-1 break-words",
                                    active && "underline decoration-periwinkle decoration-2 underline-offset-4",
                                  )}
                                >
                                  {diagram.title}
                                </span>
                                <StatusMark status={diagram.status} />
                              </Link>
                            </li>
                          );
                        })}
                      </ol>
                    </li>
                  ))}
                </ol>
              </nav>
            </div>
            <div className="mt-8 min-w-0 md:mt-0">
              <DiagramViewer key={selected.id} diagram={selected} />
              <nav aria-label="Recorrer el catálogo" className="mt-12 flex items-center justify-between gap-3">
                {previous ? (
                  <ButtonLink
                    href={diagramHref(previous.id)}
                    variant="ghost"
                    onClick={(event) => openDiagram(event, previous.id)}
                  >
                    Anterior
                  </ButtonLink>
                ) : (
                  <span />
                )}
                {next ? (
                  <ButtonLink href={diagramHref(next.id)} variant="ghost" onClick={(event) => openDiagram(event, next.id)}>
                    Siguiente
                  </ButtonLink>
                ) : (
                  <span />
                )}
              </nav>
            </div>
          </div>
        )
      )}
    </>
  );
}

export default function DiagramsPage() {
  return (
    <Suspense fallback={<DiagramsFallback />}>
      <DiagramsCatalog />
    </Suspense>
  );
}
