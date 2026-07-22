"use client";

import { useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, contradictionsByTopic, scanContradictions } from "@/lib/api-client";
import type { ContradictionScanResponse, ContradictionsResponse } from "@/lib/types";

export default function ContradictionsPage() {
  const [scanResult, setScanResult] = useState<ContradictionScanResponse | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);

  const [topic, setTopic] = useState("");
  const [byTopic, setByTopic] = useState<ContradictionsResponse | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  async function handleScan() {
    setIsScanning(true);
    setScanError(null);
    try {
      setScanResult(await scanContradictions());
    } catch (err) {
      setScanError(err instanceof ApiError ? err.detail : "No se pudo escanear.");
    } finally {
      setIsScanning(false);
    }
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    setIsSearching(true);
    setSearchError(null);
    try {
      setByTopic(await contradictionsByTopic(topic));
    } catch (err) {
      setSearchError(err instanceof ApiError ? err.detail : "No se pudo buscar.");
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold text-zinc-900 dark:text-zinc-50">Bandeja de contradicciones</h1>

      <section className="mb-8 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
        <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Escanear conocimiento reciente</h2>
        <p className="mb-3 text-sm text-zinc-500 dark:text-zinc-400">
          Revisa los nodos activos más recientes en busca de contradicciones lógicas nuevas (F2-T5). Las que confirma
          el LLM quedan registradas como relación <code>CONTRADICTS</code> en el grafo.
        </p>
        <button
          onClick={handleScan}
          disabled={isScanning}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {isScanning ? "Escaneando…" : "Escanear ahora"}
        </button>
        <ErrorBanner message={scanError} />
        {scanResult && (
          <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
            {scanResult.nodes_checked} nodos revisados · {scanResult.contradictions_detected} contradicciones nuevas detectadas.
          </p>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Buscar contradicciones por tema</h2>
        <form onSubmit={handleSearch} className="mb-4 flex gap-2">
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="tema"
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <button
            type="submit"
            disabled={isSearching}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {isSearching ? "Buscando…" : "Buscar"}
          </button>
        </form>
        <ErrorBanner message={searchError} />
        {byTopic && (
          <ul className="space-y-2">
            {byTopic.contradictions.map((c, i) => (
              <li key={i} className="rounded-md border border-zinc-200 p-3 text-sm dark:border-zinc-800">
                <p className="font-medium text-zinc-900 dark:text-zinc-50">{c.node_a_title}</p>
                <p className="my-1 text-xs font-semibold text-red-500">✕ contradice</p>
                <p className="font-medium text-zinc-900 dark:text-zinc-50">{c.node_b_title}</p>
                {c.rationale && <p className="mt-2 text-zinc-500 dark:text-zinc-400">{c.rationale}</p>}
                {c.confidence !== null && <p className="mt-1 text-xs text-zinc-400">confianza {c.confidence.toFixed(2)}</p>}
              </li>
            ))}
            {byTopic.contradictions.length === 0 && (
              <p className="text-sm italic text-zinc-400">Sin contradicciones para este tema.</p>
            )}
          </ul>
        )}
      </section>
    </div>
  );
}
