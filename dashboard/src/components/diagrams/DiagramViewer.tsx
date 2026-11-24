"use client";

import { useEffect, useRef, useState } from "react";

import { MermaidDiagram } from "@/components/diagrams/MermaidDiagram";
import { Badge, Button, Card, ErrorNotice, type Tone } from "@/components/ui";
import type { Diagram, DiagramStatus } from "@/content/diagrams";

export function statusLabel(status: DiagramStatus): string {
  if (status === "generated") return "Generado";
  if (status === "existing") return "Existente";
  return "No aplica";
}

function statusTone(status: DiagramStatus): Tone | undefined {
  if (status === "generated") return "actividad";
  if (status === "existing") return "memoria";
  return undefined;
}

export function StatusMark({ status }: { status: DiagramStatus }) {
  return (
    <span className="inline-flex shrink-0 items-center">
      {status === "generated" && <span aria-hidden="true" className="inline-block size-2.5 rounded-sm bg-obsidian" />}
      {status === "existing" && (
        <span aria-hidden="true" className="inline-block size-2.5 rounded-sm border border-obsidian bg-paper" />
      )}
      {status === "not_applicable" && (
        <span aria-hidden="true" className="font-mono text-mono text-muted">
          –
        </span>
      )}
      <span className="sr-only">{statusLabel(status)}</span>
    </span>
  );
}

function CopyCodeButton({ code }: { code: string }) {
  const [label, setLabel] = useState("Copiar código");
  const [announcement, setAnnouncement] = useState("");
  const timer = useRef<number | null>(null);
  const lastMessage = useRef("");

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    },
    [],
  );

  async function copy() {
    let ok = true;
    try {
      await navigator.clipboard.writeText(code);
    } catch {
      ok = false;
    }
    let message = ok ? "Copiado" : "No se pudo copiar";
    if (message === lastMessage.current) message += "\u00A0";
    lastMessage.current = message;
    setLabel(ok ? "Copiado" : "No se pudo copiar");
    setAnnouncement("");
    window.requestAnimationFrame(() => setAnnouncement(message));
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      setLabel("Copiar código");
      setAnnouncement("");
      timer.current = null;
    }, 2000);
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-3">
      <Button type="button" variant="ghost" onClick={() => void copy()}>
        {label}
      </Button>
      <span role="status" className="sr-only">
        {announcement}
      </span>
    </div>
  );
}

function SvgFigure({ src, caption, eager }: { src: string; caption: string; eager: boolean }) {
  const [failed, setFailed] = useState(false);
  const openLink = (
    <a
      href={src}
      target="_blank"
      rel="noreferrer"
      className="mt-2 inline-block font-mono text-mono text-slate underline decoration-periwinkle decoration-2 underline-offset-4"
    >
      Abrir en otra pestaña
    </a>
  );

  if (failed) {
    return (
      <div>
        <ErrorNotice>No se pudo mostrar la imagen de este diagrama.</ErrorNotice>
        {openLink}
      </div>
    );
  }

  return (
    <figure>
      <div className="overflow-x-auto">
        {/* SVG ya dibujado y de tamaño desconocido: next/image no puede medirlo. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={caption || "Diagrama"}
          loading={eager ? undefined : "lazy"}
          onError={() => setFailed(true)}
          className="h-auto max-w-full"
        />
      </div>
      {caption && <figcaption className="mt-2 text-caption text-slate">{caption}</figcaption>}
      {openLink}
    </figure>
  );
}

function ExistingFigures({ svgs }: { svgs: Array<{ src: string; caption: string }> }) {
  if (svgs.length === 0) {
    return <ErrorNotice>Este diagrama no tiene una imagen para mostrar.</ErrorNotice>;
  }
  return (
    <ul className="space-y-8">
      {svgs.map((svg, index) => (
        <li key={svg.src}>
          <SvgFigure src={svg.src} caption={svg.caption} eager={index === 0} />
        </li>
      ))}
    </ul>
  );
}

function DiagramBody({ diagram }: { diagram: Diagram }) {
  if (diagram.status === "generated") {
    return <MermaidDiagram code={diagram.mermaid ?? ""} label={diagram.title} />;
  }
  if (diagram.status === "existing") {
    return <ExistingFigures svgs={diagram.svgs ?? []} />;
  }
  return (
    <Card>
      <p className="text-body-sm text-obsidian">
        {diagram.reason?.trim() || "Este diagrama no describe nada que el sistema tenga hoy."}
      </p>
    </Card>
  );
}

export function DiagramViewer({ diagram }: { diagram: Diagram }) {
  return (
    <article>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-mono text-mono text-muted">{diagram.id}</span>
          <h2 className="text-heading-sm font-medium break-words text-obsidian">{diagram.title}</h2>
        </div>
        <Badge tone={statusTone(diagram.status)}>{statusLabel(diagram.status)}</Badge>
      </div>
      {diagram.description && <p className="mt-4 max-w-[40rem] text-body text-slate">{diagram.description}</p>}
      <div className="mt-8 min-w-0">
        <DiagramBody diagram={diagram} />
      </div>
      {diagram.basedOn.length > 0 && (
        <div className="mt-8">
          <h3 className="text-body-sm font-medium text-obsidian">Basado en</h3>
          <ul className="mt-2 space-y-1">
            {diagram.basedOn.map((file) => (
              <li key={file} className="font-mono text-mono break-all text-slate">
                {file}
              </li>
            ))}
          </ul>
        </div>
      )}
      {diagram.status === "generated" && diagram.mermaid && (
        <details className="mt-8">
          <summary className="cursor-pointer text-body-sm font-medium text-obsidian">Ver código Mermaid</summary>
          <div className="mt-4">
            <pre
              tabIndex={0}
              role="region"
              aria-label="Código Mermaid"
              className="max-w-full overflow-x-auto rounded-md border border-hairline bg-wash p-4"
            >
              <code className="font-mono text-mono text-obsidian">{diagram.mermaid}</code>
            </pre>
            <CopyCodeButton code={diagram.mermaid} />
          </div>
        </details>
      )}
    </article>
  );
}
