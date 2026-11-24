"use client";

import { useId, useState, type ReactNode } from "react";

import { formatNumber } from "@/components/ui";

export interface ChartPoint {
  label: string;
  value: number;
}

const MAX_BARS = 8;

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/** Más de 8 categorías: las primeras 7 y una fila Otros con el resto. Nunca pasa de 8 filas. */
function limitCategories(points: ChartPoint[]): ChartPoint[] {
  const sorted = [...points].sort(
    (a, b) => b.value - a.value || a.label.localeCompare(b.label, "es"),
  );
  if (sorted.length <= MAX_BARS) return sorted;
  const head = sorted.slice(0, MAX_BARS - 1);
  const otros = sorted.slice(MAX_BARS - 1).reduce((sum, point) => sum + point.value, 0);
  return [...head, { label: "Otros", value: otros }];
}

function seriesSummary(title: string, rows: ChartPoint[]): string {
  if (rows.length === 0) return `${title}. Sin datos.`;
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  if (total === 0) return `${title}. Sin valores en este período.`;
  const top = rows.reduce((best, row) => (row.value > best.value ? row : best));
  return `${title}. Total ${formatNumber(total)}. El mayor valor es ${formatNumber(top.value)}, en ${top.label}.`;
}

/**
 * La zona de puntero y de foco es toda la fila o la columna; la marca negra es más baja.
 * Escape oculta el recuadro sin quitar el foco. El recuadro pisa 1 px la marca para que
 * el puntero pueda entrar en él sin que desaparezca al cruzar el borde.
 */
function Mark({
  label,
  align = "center",
  className,
  children,
}: {
  label: string;
  align?: "start" | "center" | "end";
  className?: string;
  children: ReactNode;
}) {
  const tipId = useId();
  const [dismissed, setDismissed] = useState(false);
  const alignClass =
    align === "start" ? "left-0" : align === "end" ? "right-0" : "left-1/2 -translate-x-1/2";

  return (
    <div
      className={cx("group/mark relative", className)}
      onMouseEnter={() => setDismissed(false)}
      onMouseLeave={() => setDismissed(false)}
      onKeyDown={(event) => {
        if (event.key === "Escape") setDismissed(true);
      }}
    >
      <button
        type="button"
        className="absolute inset-0 z-10 rounded-md"
        aria-label={label}
        onFocus={() => setDismissed(false)}
      />
      {children}
      {!dismissed && (
        <div
          className={cx(
            "pointer-events-none absolute bottom-[calc(100%-1px)] z-20 flex pb-1 group-focus-within/mark:pointer-events-auto group-hover/mark:pointer-events-auto",
            alignClass,
          )}
        >
          <div
            id={tipId}
            role="tooltip"
            className="hidden rounded-md border border-hairline bg-paper px-2 py-1 text-caption whitespace-nowrap text-obsidian group-focus-within/mark:block group-hover/mark:block"
          >
            {label}
          </div>
        </div>
      )}
    </div>
  );
}

function DataTable({
  caption,
  categoryLabel,
  valueLabel,
  rows,
}: {
  caption: string;
  categoryLabel: string;
  valueLabel: string;
  rows: ChartPoint[];
}) {
  return (
    <details className="mt-4">
      <summary className="cursor-pointer text-caption text-slate">Ver como tabla</summary>
      <div className="mt-3 max-w-full overflow-x-auto">
        <table className="w-full border-collapse text-caption">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              <th scope="col" className="border-b border-obsidian py-2 pr-4 text-left font-medium text-obsidian">
                {categoryLabel}
              </th>
              <th scope="col" className="border-b border-obsidian py-2 text-right font-medium text-obsidian">
                {valueLabel}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={2} className="py-3 text-slate">
                  Sin datos.
                </td>
              </tr>
            ) : (
              rows.map((row, index) => (
                <tr key={`${row.label}-${index}`}>
                  <th scope="row" className="border-b border-hairline py-2 pr-4 text-left font-normal break-words text-obsidian">
                    {row.label}
                  </th>
                  <td className="border-b border-hairline py-2 text-right tabular-nums text-obsidian">
                    {formatNumber(row.value)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function BarList({
  points,
  label,
  categoryLabel = "Categoría",
  valueLabel = "Cantidad",
  emptyText = "Sin datos todavía.",
}: {
  points: ChartPoint[];
  label: string;
  categoryLabel?: string;
  valueLabel?: string;
  emptyText?: string;
}) {
  const rows = limitCategories(points.filter((point) => point.value > 0));
  const max = rows.reduce((best, row) => Math.max(best, row.value), 0);

  return (
    <figure>
      {rows.length === 0 ? (
        <p className="text-caption text-slate">{emptyText}</p>
      ) : (
        <div role="img" aria-label={seriesSummary(label, rows)} className="space-y-1">
          {rows.map((row, index) => {
            const width = max === 0 ? 0 : (row.value / max) * 100;
            const tip = `${row.label}: ${formatNumber(row.value)}`;
            return (
              <Mark key={`${row.label}-${index}`} label={tip} align="start" className="grid grid-cols-[minmax(0,7.25rem)_minmax(0,1fr)_auto] items-center gap-3">
                <span className="pointer-events-none truncate text-caption text-obsidian">{row.label}</span>
                <span aria-hidden="true" className="pointer-events-none relative block h-8">
                  <span className="absolute inset-x-0 top-1/2 h-2 -translate-y-1/2 rounded-[2px] bg-wash" />
                  <span
                    className="absolute top-1/2 left-0 h-2 -translate-y-1/2 bg-obsidian"
                    style={{ width: `${width}%`, borderRadius: 2 }}
                  />
                </span>
                <span className="pointer-events-none text-caption tabular-nums text-obsidian">
                  {formatNumber(row.value)}
                </span>
              </Mark>
            );
          })}
        </div>
      )}
      <DataTable caption={label} categoryLabel={categoryLabel} valueLabel={valueLabel} rows={rows} />
    </figure>
  );
}

export function ColumnChart({
  points,
  label,
  categoryLabel = "Día",
  valueLabel = "Cantidad",
  note,
}: {
  points: ChartPoint[];
  label: string;
  categoryLabel?: string;
  valueLabel?: string;
  note?: ReactNode;
}) {
  const max = points.reduce((best, point) => Math.max(best, point.value), 0);
  const last = points.length - 1;

  return (
    <figure className="min-w-0">
      {points.length === 0 ? (
        <p className="text-caption text-slate">Sin datos todavía.</p>
      ) : (
        <div role="img" aria-label={seriesSummary(label, points)}>
          <p className="mb-2 text-caption tabular-nums text-slate">{formatNumber(max)}</p>
          <div className="flex h-36 items-stretch gap-0.5 border-b border-hairline">
            {points.map((point, index) => {
              const height = max === 0 || point.value <= 0 ? 0 : (point.value / max) * 100;
              const align = index === 0 ? "start" : index === last ? "end" : "center";
              return (
                <Mark
                  key={`${point.label}-${index}`}
                  label={`${point.label}: ${formatNumber(point.value)}`}
                  align={align}
                  className="h-full min-w-0 flex-1"
                >
                  <span
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-x-0 bottom-0 bg-obsidian"
                    style={{ height: `${height}%`, minHeight: point.value > 0 ? 2 : 0, borderRadius: "2px 2px 0 0" }}
                  />
                </Mark>
              );
            })}
          </div>
          <div className="mt-2 flex justify-between gap-3 text-caption text-muted">
            <span>{points[0].label}</span>
            {last > 0 && <span>{points[last].label}</span>}
          </div>
        </div>
      )}
      {note && <p className="mt-3 text-caption text-slate">{note}</p>}
      <DataTable caption={label} categoryLabel={categoryLabel} valueLabel={valueLabel} rows={points} />
    </figure>
  );
}
