"use client";

import { useState } from "react";

import { EvidenceTree } from "@/components/EvidenceTree";
import { ObjectTypeBadge } from "@/components/ObjectTypeBadge";
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
  ContradictionsResponse,
  DecisionsResponse,
  PastThinkingResponse,
  PatternsResponse,
  SimilarIdeasResponse,
  SupportResponse,
} from "@/lib/types";

function WidgetCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h2 className="mb-3 text-sm font-semibold text-zinc-700 dark:text-zinc-300">{title}</h2>
      {children}
    </div>
  );
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
      setError(err instanceof ApiError ? err.detail : "Falló la consulta.");
    } finally {
      setIsLoading(false);
    }
  }
  return { result, error, isLoading, run };
}

function PastThinkingWidget() {
  const [topic, setTopic] = useState("");
  const [at, setAt] = useState("");
  const { result, error, isLoading, run } = useAsync<PastThinkingResponse>();

  return (
    <WidgetCard title="¿Qué pensaba en una fecha sobre un tema?">
      <div className="mb-3 flex flex-col gap-2">
        <input
          type="text" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="tema"
          className="rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
        <input
          type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)}
          className="rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
        <button
          onClick={() => topic && at && run(() => pastThinking(topic, new Date(at).toISOString()))}
          disabled={isLoading || !topic || !at}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {isLoading ? "Consultando…" : "Preguntar"}
        </button>
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {result && (
        <ul className="space-y-2 text-sm">
          {result.items.map((item) => (
            <li key={`${item.node_id}-${item.version}`} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
              <div className="flex items-center gap-2">
                <ObjectTypeBadge objectType={item.object_type} />
                <span className="font-medium text-zinc-900 dark:text-zinc-50">{item.title}</span>
              </div>
              <p className="line-clamp-2 text-zinc-600 dark:text-zinc-400">{item.content}</p>
              <p className="text-xs text-zinc-400">similitud {item.similarity.toFixed(2)}</p>
            </li>
          ))}
          {result.items.length === 0 && <p className="italic text-zinc-400">Sin resultados.</p>}
        </ul>
      )}
    </WidgetCard>
  );
}

function SimilarIdeasWidget() {
  const [nodeId, setNodeId] = useState("");
  const { result, error, isLoading, run } = useAsync<SimilarIdeasResponse>();

  return (
    <WidgetCard title="¿Qué ideas similares tuve antes?">
      <div className="mb-3 flex gap-2">
        <input
          type="text" value={nodeId} onChange={(e) => setNodeId(e.target.value)} placeholder="ID de nodo"
          className="flex-1 rounded-md border border-zinc-300 px-2 py-1.5 text-sm font-mono dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
        <button
          onClick={() => nodeId && run(() => similarIdeas(nodeId))}
          disabled={isLoading || !nodeId}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {isLoading ? "…" : "Preguntar"}
        </button>
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {result && (
        <ul className="space-y-2 text-sm">
          {result.items.map((item) => (
            <li key={item.node_id} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
              <div className="flex items-center gap-2">
                <ObjectTypeBadge objectType={item.object_type} />
                <span className="font-medium text-zinc-900 dark:text-zinc-50">{item.title}</span>
              </div>
              <p className="text-xs text-zinc-400">similitud {item.similarity.toFixed(2)}</p>
            </li>
          ))}
          {result.items.length === 0 && <p className="italic text-zinc-400">Sin resultados.</p>}
        </ul>
      )}
    </WidgetCard>
  );
}

function DecisionsWidget() {
  const [topic, setTopic] = useState("");
  const { result, error, isLoading, run } = useAsync<DecisionsResponse>();

  return (
    <WidgetCard title="¿Qué decisiones tomé y por qué?">
      <div className="mb-3 flex gap-2">
        <input
          type="text" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="tema"
          className="flex-1 rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
        <button
          onClick={() => topic && run(() => decisions(topic))}
          disabled={isLoading || !topic}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {isLoading ? "…" : "Preguntar"}
        </button>
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {result && (
        <ul className="space-y-2 text-sm">
          {result.decisions.map((d) => (
            <li key={d.node_id} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
              <p className="font-medium text-zinc-900 dark:text-zinc-50">{d.title}</p>
              {d.rationale && <p className="text-zinc-600 dark:text-zinc-400">Rationale: {d.rationale}</p>}
              <p className="text-xs text-zinc-400">{new Date(d.created_at).toLocaleString()}</p>
            </li>
          ))}
          {result.decisions.length === 0 && <p className="italic text-zinc-400">Sin resultados.</p>}
        </ul>
      )}
    </WidgetCard>
  );
}

function SupportWidget() {
  const [nodeId, setNodeId] = useState("");
  const { result, error, isLoading, run } = useAsync<SupportResponse>();

  return (
    <WidgetCard title="¿Qué respalda esta recomendación?">
      <div className="mb-3 flex gap-2">
        <input
          type="text" value={nodeId} onChange={(e) => setNodeId(e.target.value)} placeholder="ID de nodo"
          className="flex-1 rounded-md border border-zinc-300 px-2 py-1.5 text-sm font-mono dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
        <button
          onClick={() => nodeId && run(() => support(nodeId))}
          disabled={isLoading || !nodeId}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {isLoading ? "…" : "Preguntar"}
        </button>
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {result && (
        <ul className="space-y-2">
          {result.support.map((ev, i) => (
            <EvidenceTree key={`${ev.node_id}-${i}`} evidence={ev} depth={0} />
          ))}
          {result.support.length === 0 && <p className="text-sm italic text-zinc-400">Sin respaldo registrado.</p>}
        </ul>
      )}
    </WidgetCard>
  );
}

function ContradictionsWidget() {
  const [topic, setTopic] = useState("");
  const { result, error, isLoading, run } = useAsync<ContradictionsResponse>();

  return (
    <WidgetCard title="¿Qué contradicciones existen en mi conocimiento?">
      <div className="mb-3 flex gap-2">
        <input
          type="text" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="tema"
          className="flex-1 rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
        <button
          onClick={() => topic && run(() => contradictionsByTopic(topic))}
          disabled={isLoading || !topic}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {isLoading ? "…" : "Preguntar"}
        </button>
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {result && (
        <ul className="space-y-2 text-sm">
          {result.contradictions.map((c, i) => (
            <li key={i} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
              <p className="text-zinc-900 dark:text-zinc-50">{c.node_a_title}</p>
              <p className="text-xs text-red-500">✕ contradice</p>
              <p className="text-zinc-900 dark:text-zinc-50">{c.node_b_title}</p>
              {c.rationale && <p className="mt-1 text-xs text-zinc-500">{c.rationale}</p>}
            </li>
          ))}
          {result.contradictions.length === 0 && <p className="italic text-zinc-400">Sin contradicciones.</p>}
        </ul>
      )}
    </WidgetCard>
  );
}

function PatternsWidget() {
  const { result, error, isLoading, run } = useAsync<PatternsResponse>();

  return (
    <WidgetCard title="¿Qué patrones aparecen en mi forma de pensar?">
      <button
        onClick={() => run(() => patterns())}
        disabled={isLoading}
        className="mb-3 rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {isLoading ? "Analizando…" : "Analizar"}
      </button>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {result && (
        <div className="text-sm">
          <p className="mb-2 text-zinc-600 dark:text-zinc-400">
            {result.total_nodes} nodos analizados · tipo más común: {result.most_common_type ?? "—"}
          </p>
          <table className="w-full text-left text-xs">
            <thead className="text-zinc-400">
              <tr><th className="pr-2">Periodo</th><th className="pr-2">Tipo</th><th>Cantidad</th></tr>
            </thead>
            <tbody>
              {result.buckets.map((b, i) => (
                <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="pr-2 py-1">{b.period}</td>
                  <td className="pr-2 py-1"><ObjectTypeBadge objectType={b.object_type} /></td>
                  <td className="py-1">{b.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {result.buckets.length === 0 && <p className="italic text-zinc-400">Sin datos suficientes.</p>}
        </div>
      )}
    </WidgetCard>
  );
}

export default function CognitivePage() {
  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-zinc-900 dark:text-zinc-50">Las 7 preguntas</h1>
      <p className="mb-4 text-sm text-zinc-500 dark:text-zinc-400">
        La séptima — &quot;¿cómo llegué a esta conclusión?&quot; — vive en{" "}
        <a href="/explain" className="text-blue-600 hover:underline dark:text-blue-400">Razonamiento</a>.
      </p>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <PastThinkingWidget />
        <SimilarIdeasWidget />
        <DecisionsWidget />
        <SupportWidget />
        <ContradictionsWidget />
        <PatternsWidget />
      </div>
    </div>
  );
}
