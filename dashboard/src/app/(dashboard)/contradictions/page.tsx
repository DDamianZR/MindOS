"use client";

import { useState } from "react";

import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorNotice,
  MonoLabel,
  PageHeader,
  SectionTitle,
  Skeleton,
  formatNumber,
} from "@/components/ui";
import { ApiError, contradictionsByTopic, scanContradictions } from "@/lib/api-client";
import type { ContradictionPair, ContradictionScanResponse, ContradictionsResponse } from "@/lib/types";

const INPUT_CLASS =
  "h-10 w-full min-w-0 rounded-md border border-hairline bg-paper px-3 text-body-sm text-obsidian placeholder:text-muted";

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.detail) return `${err.detail} ${fallback}`;
  return fallback;
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
      setScanError(describeError(err, "Inténtalo de nuevo en un momento."));
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
      setSearchError(describeError(err, "Revisa el tema e inténtalo de nuevo."));
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Contradicciones"
        continuation="donde tu memoria no cuadra"
        description="Busca un tema o revisa lo que guardaste hace poco."
      />

      <Card>
        <SectionTitle>Revisar lo reciente</SectionTitle>
        <p className="max-w-[40rem] text-body-sm text-slate">
          Mira lo que guardaste hace poco y marca las ideas que no cuadran entre sí.
        </p>
        <div className="mt-5">
          <Button type="button" onClick={handleScan} disabled={isScanning}>
            {isScanning ? "Revisando…" : "Revisar ahora"}
          </Button>
        </div>
        {isScanning && (
          <div className="mt-4" aria-live="polite">
            <p className="text-caption text-slate">Revisando tu memoria. Espera un momento.</p>
            <Skeleton className="mt-3 h-8 w-full max-w-md" />
          </div>
        )}
        {scanError && (
          <div className="mt-4">
            <ErrorNotice>{scanError}</ErrorNotice>
          </div>
        )}
        {scanResult && (
          <p className="mt-4 text-body-sm text-slate">
            {formatNumber(scanResult.nodes_checked)} recuerdos revisados.{" "}
            {formatNumber(scanResult.contradictions_detected)} contradicciones nuevas.
            {scanResult.contradictions_detected > 0 && " Búscalas por tema para verlas."}
          </p>
        )}
      </Card>

      <section className="mt-16">
        <SectionTitle>Buscar por tema</SectionTitle>
        <form
          onSubmit={handleSearch}
          aria-label="Buscar contradicciones por tema"
          className="flex flex-col gap-4 sm:flex-row sm:items-end"
        >
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <label htmlFor="contradiction-topic" className="text-caption text-slate">
              Tema
            </label>
            <input
              id="contradiction-topic"
              type="text"
              required
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Por ejemplo, sueño o trabajo"
              enterKeyHint="search"
              className={INPUT_CLASS}
            />
          </div>
          <Button type="submit" disabled={isSearching}>
            {isSearching ? "Buscando…" : "Buscar"}
          </Button>
        </form>

        {searchError && (
          <div className="mt-4">
            <ErrorNotice>{searchError}</ErrorNotice>
          </div>
        )}

        {isSearching && (
          <div className="mt-6" aria-live="polite">
            <p className="text-caption text-slate">Buscando contradicciones. Espera un momento.</p>
            <Skeleton className="mt-3 h-28 w-full" />
          </div>
        )}

        {!isSearching && byTopic && (
          <div className="mt-8">
            {byTopic.contradictions.length === 0 ? (
              <EmptyState
                title="No hay contradicciones para este tema."
                action={
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => document.getElementById("contradiction-topic")?.focus()}
                  >
                    Probar otro tema
                  </Button>
                }
              >
                Prueba con otras palabras, o revisa lo que guardaste hace poco.
              </EmptyState>
            ) : (
              <ul className="space-y-4">
                {byTopic.contradictions.map((pair) => (
                  <ContradictionCard key={`${pair.node_a_id}-${pair.node_b_id}`} pair={pair} />
                ))}
              </ul>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
