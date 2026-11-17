"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ApprovalIcon,
  AssistantIcon,
  BrandMark,
  CaptureIcon,
  CloseIcon,
  ContradictionIcon,
  GraphIcon,
  MenuIcon,
  QuestionsIcon,
  ReasoningIcon,
  SearchIcon,
  TimelineIcon,
} from "@/components/icons";
import { useAuth } from "@/lib/auth";

// Agrupado por lo que la persona viene a hacer, no por cómo está construido el backend:
// conversar, consultar lo guardado, entender cómo se llegó a algo, y lo que espera su decisión.
const NAV_GROUPS = [
  {
    label: null,
    items: [{ href: "/assistant", label: "Asistente", icon: AssistantIcon }],
  },
  {
    label: "Memoria",
    items: [
      { href: "/search", label: "Buscar", icon: SearchIcon },
      { href: "/graph", label: "Grafo", icon: GraphIcon },
      { href: "/timeline", label: "Línea de tiempo", icon: TimelineIcon },
      { href: "/capture", label: "Capturar", icon: CaptureIcon },
    ],
  },
  {
    label: "Pensamiento",
    items: [
      { href: "/explain", label: "Razonamiento", icon: ReasoningIcon },
      { href: "/cognitive", label: "Siete preguntas", icon: QuestionsIcon },
      { href: "/contradictions", label: "Contradicciones", icon: ContradictionIcon },
    ],
  },
  {
    label: "Pendiente",
    items: [{ href: "/approvals", label: "Aprobaciones", icon: ApprovalIcon }],
  },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex-1 space-y-5 overflow-y-auto px-3 pb-4">
      {NAV_GROUPS.map((group, index) => (
        <div key={group.label ?? index}>
          {group.label && <p className="mb-1 px-2.5 text-xs text-ink-faint">{group.label}</p>}
          <ul className="space-y-px">
            {group.items.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              const ItemIcon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={`flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm ${
                      active
                        ? "bg-ink font-medium text-paper"
                        : "text-ink-soft hover:bg-rule hover:text-ink"
                    }`}
                  >
                    <ItemIcon className="shrink-0" />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

function Brand() {
  return (
    <Link href="/assistant" className="flex items-center gap-2 text-ink">
      <BrandMark className="text-accent" />
      <span className="font-serif text-xl font-semibold tracking-tight">MindOS</span>
    </Link>
  );
}

function Account() {
  const { username, logout } = useAuth();
  return (
    <div className="flex items-center justify-between gap-2 border-t border-rule px-5 py-3 text-sm">
      <span className="truncate text-ink-soft">{username}</span>
      <button onClick={logout} className="shrink-0 text-ink-faint hover:text-ink hover:underline">
        Cerrar sesión
      </button>
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);

  // En móvil el menú es un panel superpuesto: Escape lo cierra, igual que cualquier diálogo.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setIsOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen]);

  const currentLabel =
    NAV_GROUPS.flatMap((g) => g.items).find((i) => pathname === i.href || pathname.startsWith(`${i.href}/`))?.label ??
    "MindOS";

  return (
    <>
      {/* Escritorio: columna fija */}
      <nav
        aria-label="Principal"
        className="hidden w-60 shrink-0 flex-col border-r border-rule md:flex"
      >
        <div className="px-5 pt-5 pb-6">
          <Brand />
        </div>
        <NavLinks />
        <Account />
      </nav>

      {/* Móvil: barra superior + panel */}
      <header className="flex items-center justify-between border-b border-rule px-4 py-2.5 md:hidden">
        <Brand />
        <button
          onClick={() => setIsOpen(true)}
          aria-expanded={isOpen}
          aria-controls="mobile-nav"
          className="-mr-1.5 flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-ink-soft"
        >
          {currentLabel}
          <MenuIcon />
          <span className="sr-only">Abrir menú</span>
        </button>
      </header>

      {isOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            aria-label="Cerrar menú"
            onClick={() => setIsOpen(false)}
            className="absolute inset-0 bg-ink/40"
          />
          <nav
            id="mobile-nav"
            aria-label="Principal"
            className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-paper shadow-xl"
          >
            <div className="flex items-center justify-between px-5 pt-5 pb-6">
              <Brand />
              <button
                onClick={() => setIsOpen(false)}
                className="-mr-1.5 rounded-md p-1.5 text-ink-soft"
              >
                <CloseIcon />
                <span className="sr-only">Cerrar menú</span>
              </button>
            </div>
            <NavLinks onNavigate={() => setIsOpen(false)} />
            <Account />
          </nav>
        </div>
      )}
    </>
  );
}
