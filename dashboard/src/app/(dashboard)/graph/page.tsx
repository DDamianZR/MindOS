"use client";

import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { useEffect, useRef, useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { NodeDetailPanel } from "@/components/NodeDetailPanel";
import { ApiError, getNodeHistory, getNodeNeighbors } from "@/lib/api-client";
import { objectTypeColor, relationLabel } from "@/lib/object-type-style";

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
        const cy = cytoscape({
          container: containerRef.current,
          elements,
          style: [
            {
              selector: "node",
              style: {
                "background-color": "data(color)",
                label: "data(label)",
                color: "#27272a",
                "font-size": 10,
                "text-valign": "bottom",
                "text-margin-y": 4,
                width: 28,
                height: 28,
              },
            },
            {
              selector: `node[id = "${seedNodeId}"]`,
              style: { "border-width": 3, "border-color": "#ef4444" },
            },
            {
              selector: "edge",
              style: {
                width: 1.5,
                "line-color": "#a1a1aa",
                "target-arrow-color": "#a1a1aa",
                "target-arrow-shape": "triangle",
                "curve-style": "bezier",
                label: "data(label)",
                "font-size": 8,
                color: "#71717a",
              },
            },
          ],
          layout: { name: "cose", animate: false },
        });
        cy.on("tap", "node", (evt) => setSelectedNodeId(evt.target.id()));
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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (inputValue.trim()) setSeedNodeId(inputValue.trim());
  }

  function handleNavigate(nodeId: string) {
    setSelectedNodeId(nodeId);
    setSeedNodeId(nodeId);
    setInputValue(nodeId);
  }

  return (
    <div className="flex h-full flex-col">
      <h1 className="mb-4 text-xl font-semibold text-zinc-900 dark:text-zinc-50">Grafo de conocimiento</h1>

      <form onSubmit={handleSubmit} className="mb-4 flex gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="ID de nodo semilla (UUID) — cópialo desde Búsqueda"
          className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm font-mono dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
        <select
          value={depth}
          onChange={(e) => setDepth(Number(e.target.value))}
          className="rounded-md border border-zinc-300 px-2 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        >
          {[1, 2, 3].map((d) => (
            <option key={d} value={d}>profundidad {d}</option>
          ))}
        </select>
        <button
          type="submit"
          disabled={isLoading}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {isLoading ? "Cargando…" : "Explorar"}
        </button>
      </form>

      <ErrorBanner message={error} />
      {!seedNodeId && (
        <p className="text-sm text-zinc-400 italic">
          Pega el ID de un nodo (visible en Búsqueda o Contradicciones) para empezar a explorar el grafo.
        </p>
      )}

      <div className="flex min-h-0 flex-1 gap-4">
        <div
          ref={containerRef}
          className="min-w-0 flex-1 rounded-md border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
        />
        {selectedNodeId && (
          <NodeDetailPanel nodeId={selectedNodeId} onClose={() => setSelectedNodeId(null)} onNavigate={handleNavigate} />
        )}
      </div>
    </div>
  );
}
