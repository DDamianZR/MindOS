"use client";

import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { NodeDetailPanel } from "@/components/NodeDetailPanel";
import { Badge, Button, EmptyState, ErrorNotice, MonoLabel, PageHeader, Skeleton } from "@/components/ui";
import { ApiError, getNodeHistory, getNodeNeighbors } from "@/lib/api-client";
import { OBJECT_FAMILY_HEX, objectTypeColor, relationLabel } from "@/lib/object-type-style";

const FIELD =
  "h-10 w-full rounded-md border border-hairline bg-paper px-3 text-body-sm text-obsidian placeholder:text-muted focus:border-obsidian";

async function buildElements(seedNodeId: string, depth: number): Promise<ElementDefinition[]> {
  const neighbors = await getNodeNeighbors(seedNodeId, depth);

  const nodeIds = new Set<string>([seedNodeId]);
  for (const edge of neighbors.neighbors) {
    nodeIds.add(edge.source_id);
    nodeIds.add(edge.target_id);
  }

  const nodeInfos = await Promise.all(
    [...nodeIds].map(async (id) => {
      try {
        const history = await getNodeHistory(id);
        const latest = history.versions[history.versions.length - 1];
        return { id, title: latest?.title ?? id, objectType: history.object_type as string };
      } catch {
        return { id, title: id, objectType: null as string | null };
      }
    }),
  );

  const nodeElements: ElementDefinition[] = nodeInfos.map((n) => ({
    data: {
      id: n.id,
      label: n.title.length > 24 ? `${n.title.slice(0, 24)}…` : n.title,
      color: objectTypeColor(n.objectType),
    },
  }));

  const edgeElements: ElementDefinition[] = neighbors.neighbors.map((e, i) => ({
    data: {
      id: `e${i}-${e.source_id}-${e.target_id}`,
      source: e.source_id,
      target: e.target_id,
      label: relationLabel(e.relation_type),
    },
  }));

  return [...nodeElements, ...edgeElements];
}

export default function GraphPage() {
  const nodeFieldId = useId();
  const nodeHintId = useId();
  const depthId = useId();
  const nodeInputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [seedNodeId, setSeedNodeId] = useState("");
  const [inputValue, setInputValue] = useState("");
  const [depth, setDepth] = useState(2);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!seedNodeId || !containerRef.current) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    buildElements(seedNodeId, depth)
      .then((elements) => {
        if (cancelled || !containerRef.current) return;
        cyRef.current?.destroy();
        // Cytoscape no hereda la fuente del documento: hay que pasársela medida.
        const fontFamily = getComputedStyle(document.body).fontFamily;
        const cy = cytoscape({
          container: containerRef.current,
          elements,
          style: [
            {
              selector: "node",
              style: {
                "background-color": "data(color)",
                "border-width": 1,
                "border-color": OBJECT_FAMILY_HEX.border,
                "border-style": "solid",
                label: "data(label)",
                color: OBJECT_FAMILY_HEX.text,
                "font-family": fontFamily,
                "font-size": 13,
                "font-weight": 500,
                "text-valign": "bottom",
                "text-margin-y": 6,
                "overlay-opacity": 0,
                width: 32,
                height: 32,
              },
            },
            {
              selector: "node:selected",
              style: {
                "border-width": 3,
                "border-color": OBJECT_FAMILY_HEX.selectedBorder,
                "overlay-opacity": 0,
              },
            },
            {
              selector: "edge",
              style: {
                width: 1,
                "line-color": OBJECT_FAMILY_HEX.edge,
                "target-arrow-color": OBJECT_FAMILY_HEX.edge,
                "target-arrow-shape": "triangle",
                "curve-style": "bezier",
                label: "data(label)",
                "font-family": fontFamily,
                "font-size": 10,
                color: OBJECT_FAMILY_HEX.edge,
                "text-rotation": "autorotate",
              },
            },
          ],
          layout: { name: "cose", animate: false },
        });
        cy.on("tap", "node", (evt) => setSelectedNodeId(evt.target.id()));
        cy.getElementById(seedNodeId).select();
        cyRef.current = cy;
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : "No se pudo cargar el grafo.");
      })
      .finally(() => !cancelled && setIsLoading(false));

    return () => {
      cancelled = true;
    };
  }, [seedNodeId, depth]);

  useEffect(() => () => cyRef.current?.destroy(), []);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const id = inputValue.trim();
    if (!id) {
      nodeInputRef.current?.setCustomValidity("Escribe el identificador de una nota.");
      nodeInputRef.current?.reportValidity();
      return;
    }
    nodeInputRef.current?.setCustomValidity("");
    setSeedNodeId(id);
  }

  function handleNavigate(nodeId: string) {
    setSelectedNodeId(nodeId);
    setSeedNodeId(nodeId);
    setInputValue(nodeId);
  }

  return (
    <div className="flex min-h-[70vh] flex-col">
      <PageHeader
        title="Grafo"
        continuation="cómo se conecta lo que sabes"
        description="Parte de una nota y mira con qué más se conecta."
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
            className={`${FIELD} font-mono`}
          />
        </div>
        <div className="flex w-full flex-col gap-1.5 sm:w-40">
          <label htmlFor={depthId} className="text-body-sm font-medium text-obsidian">
            Alcance
          </label>
          <select
            id={depthId}
            name="depth"
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
            className={FIELD}
          >
            {[1, 2, 3].map((d) => (
              <option key={d} value={d}>
                {d === 1 ? "Un paso" : d === 2 ? "Dos pasos" : "Tres pasos"}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" disabled={isLoading} className="h-10 w-full sm:w-auto">
          {isLoading ? "Cargando…" : "Explorar"}
        </Button>
      </form>

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <MonoLabel className="text-muted">Familias</MonoLabel>
        <Badge tone="memoria">Memoria</Badge>
        <Badge tone="pensamiento">Pensamiento</Badge>
      </div>
      <p className="mt-3 text-caption text-slate">El color del nodo dice si es memoria o pensamiento.</p>

      {error && (
        <div className="mt-6">
          <ErrorNotice>{error} Revisa la conexión y vuelve a intentarlo.</ErrorNotice>
        </div>
      )}

      {!seedNodeId && !error && (
        <div className="mt-12">
          <EmptyState
            title="Todavía no hay un grafo"
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

      {seedNodeId && (
        <div className="mt-6 flex min-h-0 flex-1 flex-col gap-4 lg:flex-row lg:items-stretch">
          <div className="relative min-h-[420px] min-w-0 flex-1" aria-busy={isLoading}>
            <p className="pointer-events-none absolute m-[-1px] h-px w-px overflow-hidden border-0 p-0 whitespace-nowrap [clip-path:inset(50%)]">
              Grafo con las notas conectadas. Elige un nodo para leer su detalle en el panel.
            </p>
            <div
              ref={containerRef}
              className="absolute inset-0 rounded-md border border-hairline bg-paper"
            />
            {isLoading && (
              <div className="absolute inset-0 p-4">
                <Skeleton className="h-full w-full" />
              </div>
            )}
          </div>
          {selectedNodeId && (
            <NodeDetailPanel
              nodeId={selectedNodeId}
              onClose={() => setSelectedNodeId(null)}
              onNavigate={handleNavigate}
            />
          )}
        </div>
      )}
    </div>
  );
}
