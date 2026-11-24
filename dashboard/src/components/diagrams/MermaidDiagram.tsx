"use client";

import { useEffect, useId, useRef, useState } from "react";

import { Button, ErrorNotice, Skeleton } from "@/components/ui";

export type MermaidResult = { ok: true } | { ok: false; message: string };

// Una sola initialize: cada llamada pisa la config global de la librería.
let mermaidPromise: Promise<typeof import("mermaid").default> | null = null;
let renderSeq = 0;

function nextRenderId(): string {
  renderSeq += 1;
  // El id entra en un selector (`#id`): único y con letra inicial.
  return `mindosMermaid${renderSeq}`;
}

function loadMermaid(): Promise<typeof import("mermaid").default> {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid")
      .then((mod) => {
        const mermaid = mod.default;
        const fontFamily = getComputedStyle(document.body).fontFamily;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          // El gráfico de error de la librería no es el aviso de esta vista.
          suppressErrorRendering: true,
          darkMode: false,
          theme: "base",
          fontFamily,
          themeVariables: {
            fontFamily,
            fontSize: "14px",
            primaryColor: "#ffffff",
            primaryBorderColor: "#000000",
            primaryTextColor: "#000000",
            lineColor: "#4d4d4d",
            secondaryColor: "#c1dff9",
            tertiaryColor: "#f5f5f5",
            clusterBkg: "#fafafa",
            clusterBorder: "#d6d6d6",
            noteBkgColor: "#fde3f6",
            noteBorderColor: "#d6d6d6",
            actorBkg: "#ffffff",
            actorBorder: "#000000",
          },
        });
        return mermaid;
      })
      .catch((err: unknown) => {
        mermaidPromise = null;
        throw err;
      });
  }
  return mermaidPromise;
}

function messageOf(err: unknown): string {
  if (typeof err === "string" && err.trim()) return err.trim();
  if (err instanceof Error && err.message.trim()) return err.message.trim();
  if (err && typeof err === "object") {
    const record = err as { str?: unknown; message?: unknown };
    if (typeof record.str === "string" && record.str.trim()) return record.str.trim();
    if (typeof record.message === "string" && record.message.trim()) return record.message.trim();
  }
  return "No se pudo leer el error.";
}

function removeMermaidLeftovers(id: string, host: HTMLElement) {
  for (const candidate of [id, `d${id}`, `i${id}`]) {
    const node = document.getElementById(candidate);
    if (node && !host.contains(node)) node.remove();
  }
}

function prefixSvgIds(root: SVGSVGElement, prefix: string) {
  const nodes = [root, ...root.querySelectorAll<Element>("[id]")];
  const map = new Map<string, string>();
  for (const node of nodes) {
    if (node.id && !map.has(node.id)) map.set(node.id, `${prefix}-${node.id}`);
  }
  for (const node of nodes) {
    const next = node.id ? map.get(node.id) : undefined;
    if (next) node.id = next;
  }
  const ordered = [...map.entries()].sort((a, b) => b[0].length - a[0].length);
  const rewrite = (value: string) => {
    let next = value;
    for (const [oldId, newId] of ordered) next = next.replaceAll(`#${oldId}`, `#${newId}`);
    return next;
  };
  for (const node of [root, ...root.querySelectorAll<Element>("*")]) {
    for (const attr of node.getAttributeNames()) {
      const value = node.getAttribute(attr);
      if (!value || !value.includes("#")) continue;
      const next = rewrite(value);
      if (next !== value) node.setAttribute(attr, next);
    }
  }
  for (const style of root.querySelectorAll("style")) {
    const css = style.textContent;
    if (!css || !css.includes("#")) continue;
    style.textContent = rewrite(css);
  }
}

function presentSvg(markup: string, fit: "contain" | "natural"): SVGSVGElement {
  const doc = new DOMParser().parseFromString(markup, "image/svg+xml");
  const root = doc.documentElement;
  if (root.localName !== "svg" || doc.querySelector("parsererror")) {
    throw new Error("El dibujo no devolvió un SVG válido.");
  }
  const imported = document.importNode(root, true);
  if (!(imported instanceof SVGSVGElement)) {
    throw new Error("El dibujo no devolvió un SVG válido.");
  }
  if (fit === "natural") prefixSvgIds(imported, "full");

  const widthAttr = imported.getAttribute("width");
  const heightAttr = imported.getAttribute("height");
  const width = widthAttr ? Number.parseFloat(widthAttr) : Number.NaN;
  const height = heightAttr ? Number.parseFloat(heightAttr) : Number.NaN;
  if (!imported.getAttribute("viewBox") && Number.isFinite(width) && Number.isFinite(height)) {
    imported.setAttribute("viewBox", `0 0 ${width} ${height}`);
  }

  if (fit === "contain") {
    imported.removeAttribute("width");
    imported.removeAttribute("height");
    imported.style.maxWidth = "100%";
    imported.style.width = "100%";
    imported.style.height = "auto";
  } else {
    imported.style.maxWidth = "none";
    imported.style.height = "auto";
    if (Number.isFinite(width)) imported.style.width = `${width}px`;
  }
  return imported;
}

export function MermaidDiagram({
  code,
  label,
  quiet = false,
  onSettled,
}: {
  code: string;
  label: string;
  /** Sin botón de pantalla completa: lo usa la revisión, que dibuja fuera de la vista. */
  quiet?: boolean;
  onSettled?: (result: MermaidResult) => void;
}) {
  const titleId = useId();
  const inlineRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const dialogHostRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<string | null>(null);
  const onSettledRef = useRef(onSettled);
  const [phase, setPhase] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onSettledRef.current = onSettled;
  }, [onSettled]);

  useEffect(() => {
    const host = inlineRef.current;
    if (!host) return;
    const report = onSettledRef.current;
    let cancelled = false;
    const id = nextRenderId();

    (async () => {
      if (!code.trim()) {
        if (cancelled) return;
        const message = "El diagrama no incluye código.";
        host.replaceChildren();
        svgRef.current = null;
        setError(message);
        setPhase("error");
        report?.({ ok: false, message });
        return;
      }
      try {
        const mermaid = await loadMermaid();
        const { svg, bindFunctions } = await mermaid.render(id, code, host);
        if (cancelled) return;
        if (!svg.trim()) throw new Error("El dibujo volvió vacío.");
        host.replaceChildren(presentSvg(svg, "contain"));
        try {
          bindFunctions?.(host);
        } catch {
          // Con securityLevel strict no hay interacción. Si el enlace falla, el SVG ya está.
        }
        svgRef.current = svg;
        setError(null);
        setPhase("ready");
        report?.({ ok: true });
      } catch (err) {
        if (cancelled) return;
        host.replaceChildren();
        svgRef.current = null;
        const message = messageOf(err);
        setError(message);
        setPhase("error");
        report?.({ ok: false, message });
      } finally {
        removeMermaidLeftovers(id, host);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [code]);

  function openFullscreen() {
    const dialog = dialogRef.current;
    const host = dialogHostRef.current;
    const markup = svgRef.current;
    if (!dialog || !host || !markup || dialog.open) return;
    try {
      host.replaceChildren(presentSvg(markup, "natural"));
    } catch {
      host.textContent = "No se pudo ampliar este diagrama.";
    }
    dialog.showModal();
    host.focus();
  }

  const showRegion = phase === "ready" && !quiet;

  return (
    <div>
      {phase === "loading" && <Skeleton className="h-48 w-full" />}
      <div
        ref={inlineRef}
        tabIndex={showRegion ? 0 : undefined}
        role={showRegion ? "region" : undefined}
        aria-label={showRegion ? `Diagrama: ${label}` : undefined}
        className="overflow-x-auto [&_svg]:block [&_svg]:h-auto [&_svg]:max-w-full"
      />
      {phase === "error" && error && (
        <div>
          <ErrorNotice>Este diagrama tiene un error de sintaxis y no se pudo dibujar.</ErrorNotice>
          <details className="mt-3">
            <summary className="cursor-pointer text-caption text-slate">Detalle técnico</summary>
            <pre
              tabIndex={0}
              role="region"
              aria-label="Detalle técnico del error"
              className="mt-2 max-w-full overflow-x-auto rounded-md border border-hairline bg-wash p-3 font-mono text-mono whitespace-pre-wrap break-words text-slate"
            >
              <code>{error}</code>
            </pre>
          </details>
        </div>
      )}
      {!quiet && phase === "ready" && (
        <>
          <div className="mt-4">
            <Button type="button" variant="ghost" onClick={openFullscreen}>
              Ver a pantalla completa
            </Button>
          </div>
          {/* El diálogo nativo cierra con Escape y devuelve el foco. No hace falta un listener. */}
          <dialog
            ref={dialogRef}
            aria-labelledby={titleId}
            onClose={() => dialogHostRef.current?.replaceChildren()}
            className="max-h-[calc(100dvh-2rem)] max-w-[calc(100dvw-2rem)] rounded-md border border-hairline bg-paper p-5 text-left text-obsidian overscroll-contain [&::backdrop]:overflow-hidden [&::backdrop]:bg-obsidian/20 [&::backdrop]:overscroll-contain"
          >
            <div className="sticky top-0 z-10 mb-4 flex items-start justify-between gap-4 bg-paper py-1">
              <h2 id={titleId} className="text-subheading font-medium">
                A pantalla completa
              </h2>
              <form method="dialog">
                <Button type="submit" variant="ghost">
                  Cerrar
                </Button>
              </form>
            </div>
            <div
              ref={dialogHostRef}
              tabIndex={0}
              aria-label="Diagrama a tamaño natural"
              className="overflow-auto overscroll-contain"
            />
          </dialog>
        </>
      )}
    </div>
  );
}
