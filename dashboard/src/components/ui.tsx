// Kit de interfaz de MindOS. Todas las vistas se arman con estas piezas para que el sistema
// visual (4 px, sin sombras, mono para etiquetas, pastel por categoría) se mantenga solo.
import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/** Contenedor de página: 1200 px de ancho máximo y 20 px de margen lateral. */
export function Container({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cx("mx-auto w-full max-w-[1200px] px-5", className)}>{children}</div>;
}

// --- Botones ---

type ButtonVariant = "primary" | "ghost" | "ghost-dark";

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-1.5 rounded-md px-4 py-2 font-mono text-mono font-medium uppercase whitespace-nowrap disabled:cursor-not-allowed disabled:opacity-50";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-obsidian text-paper",
  ghost: "border border-hairline text-slate hover:text-obsidian hover:border-obsidian",
  "ghost-dark": "border border-midnight-line text-paper/80 hover:text-paper hover:border-paper/60",
};

export function Button({
  variant = "primary",
  className,
  ...props
}: ComponentProps<"button"> & { variant?: ButtonVariant }) {
  return <button className={cx(BUTTON_BASE, BUTTON_VARIANTS[variant], className)} {...props} />;
}

export function ButtonLink({
  variant = "primary",
  className,
  ...props
}: ComponentProps<typeof Link> & { variant?: ButtonVariant }) {
  return <Link className={cx(BUTTON_BASE, BUTTON_VARIANTS[variant], className)} {...props} />;
}

// --- Etiquetas ---

/** Etiqueta mono en mayúsculas (11 px). Para categorías, metadatos técnicos y encabezados de datos. */
export function MonoLabel({ className, children }: { className?: string; children: ReactNode }) {
  return <span className={cx("mono-label", className)}>{children}</span>;
}

/** Insignia: etiqueta mono con borde fino. `tone` la rellena con el pastel de su categoría. */
export function Badge({
  tone,
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cx(
        "mono-label inline-flex items-center rounded-md px-1.5 py-0.5",
        tone ? TONE_FILL[tone] : "border border-hairline text-slate",
        className,
      )}
    >
      {children}
    </span>
  );
}

// --- Encabezados ---

/**
 * Encabezado de vista: una línea en peso 500 y, opcionalmente, una continuación en peso 400 y
 * gris (el patrón "una línea fuerte + una ligera"). `size="display"` solo para portadas.
 */
export function PageHeader({
  title,
  continuation,
  description,
  actions,
  size = "heading",
}: {
  title: ReactNode;
  continuation?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  size?: "display" | "heading";
}) {
  const titleSize = size === "display" ? "text-heading md:text-display" : "text-heading-sm md:text-heading";
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-6">
      <div className="max-w-[46rem]">
        <h1 className={cx(titleSize, "font-medium text-obsidian")}>
          {title}
          {continuation && (
            <>
              <br />
              <span className="font-normal text-slate">{continuation}</span>
            </>
          )}
        </h1>
        {description && <p className="mt-4 max-w-[40rem] text-body text-slate">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

/** Título de sección con el guion periwinkle a la izquierda. */
export function SectionTitle({
  children,
  aside,
  dark = false,
}: {
  children: ReactNode;
  aside?: ReactNode;
  dark?: boolean;
}) {
  return (
    <div className="mb-5 flex items-baseline justify-between gap-4">
      <h2
        className={cx(
          "flex items-center gap-3 text-subheading font-medium",
          dark ? "text-paper" : "text-obsidian",
        )}
      >
        <span aria-hidden="true" className="inline-block h-0.5 w-4 bg-periwinkle" />
        {children}
      </h2>
      {aside && <div className={cx("text-caption", dark ? "text-paper/70" : "text-slate")}>{aside}</div>}
    </div>
  );
}

// --- Tarjetas ---

/** Categoría que etiqueta un pastel. Cada pastel significa siempre lo mismo en toda la app. */
export type Tone = "memoria" | "pensamiento" | "agente" | "actividad";

export const TONE_FILL: Record<Tone, string> = {
  memoria: "bg-sky text-obsidian",
  pensamiento: "bg-blush text-obsidian",
  agente: "bg-peach text-obsidian",
  actividad: "bg-mint text-obsidian",
};

/** Tarjeta blanca con borde fino. La superficie por defecto para agrupar contenido. */
export function Card({
  className,
  children,
  as: Tag = "div",
}: {
  className?: string;
  children: ReactNode;
  as?: "div" | "section" | "article" | "li";
}) {
  return <Tag className={cx("rounded-md border border-hairline bg-paper p-5", className)}>{children}</Tag>;
}

/**
 * Métrica destacada: el relleno pastel ES la tarjeta (sin borde ni sombra). Etiqueta mono arriba
 * con flecha opcional, cifra grande, una línea de contexto debajo.
 */
export function StatCard({
  tone,
  label,
  value,
  caption,
  trend,
}: {
  tone: Tone;
  label: string;
  value: ReactNode;
  caption?: ReactNode;
  trend?: "up" | "down";
}) {
  return (
    <div className={cx("flex min-h-[180px] flex-col justify-between rounded-md p-6", TONE_FILL[tone])}>
      <MonoLabel>
        {trend === "up" && "↑ "}
        {trend === "down" && "↓ "}
        {label}
      </MonoLabel>
      <div>
        <p className="mt-6 text-heading font-medium tabular-nums md:text-display">{value}</p>
        {caption && <p className="mt-1 text-caption text-slate">{caption}</p>}
      </div>
    </div>
  );
}

/** Selector por pestañas grandes: la activa toma el relleno menta, sin borde ni sombra extra. */
export function TabCards<T extends string>({
  tabs,
  active,
  onChange,
  label,
}: {
  tabs: Array<{ id: T; label: string; count?: number }>;
  active: T;
  onChange: (id: T) => void;
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {tabs.map((tab) => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab.id)}
            className={cx(
              "rounded-md border px-4 py-5 text-center text-subheading font-medium",
              selected ? "border-transparent bg-mint text-obsidian" : "border-hairline bg-paper text-slate hover:text-obsidian",
            )}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className="mt-1 block font-mono text-mono-sm text-slate">{tab.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// --- Banda oscura ---

/**
 * La única superficie invertida de una página: azul medianoche a todo el ancho. Úsala como
 * máximo una vez por vista, para el contenido que muestra profundidad de trabajo.
 */
export function DarkBand({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <section className={cx("bg-midnight py-16 text-paper md:py-20", className)}>
      <Container>{children}</Container>
    </section>
  );
}

/** Tarjeta sobre la banda oscura, con el guion periwinkle en el borde izquierdo. */
export function PaperCard({
  badge,
  title,
  meta,
  href,
}: {
  badge: string;
  title: string;
  meta?: ReactNode;
  href?: string;
}) {
  const body = (
    <>
      <span aria-hidden="true" className="absolute top-8 left-0 h-6 w-0.5 bg-periwinkle" />
      <span className="mono-label text-paper/80">{badge}</span>
      <span className="mt-4 block text-subheading font-medium text-paper">{title}</span>
      {meta && <span className="mt-4 block font-mono text-mono-sm text-paper/55">{meta}</span>}
    </>
  );
  const className = "relative block h-full rounded-md bg-midnight-card p-7";
  return href ? (
    <Link href={href} className={cx(className, "hover:bg-[#15154a]")}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}

// --- Estados ---

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-hairline px-6 py-10">
      <p className="text-subheading font-medium text-obsidian">{title}</p>
      {children && <p className="mt-2 max-w-[36rem] text-body-sm text-slate">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorNotice({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="rounded-md border border-danger/30 bg-[#fef3f2] px-4 py-3 text-caption text-danger">
      {children}
    </p>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx("animate-pulse rounded-md bg-wash", className)} />;
}

// --- Formato ---

const NUMBER = new Intl.NumberFormat("es");
const COMPACT = new Intl.NumberFormat("es", { notation: "compact", maximumFractionDigits: 1 });

export function formatNumber(value: number, compact = false): string {
  return compact && Math.abs(value) >= 10_000 ? COMPACT.format(value) : NUMBER.format(value);
}

export function formatUsd(value: number): string {
  return new Intl.NumberFormat("es", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: value < 1 ? 3 : 2,
    maximumFractionDigits: value < 1 ? 3 : 2,
  }).format(value);
}
