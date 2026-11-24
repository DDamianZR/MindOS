"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { CloseIcon, MenuIcon } from "@/components/icons";
import { ButtonLink, Container } from "@/components/ui";
import { type AssistantStatus, getAssistantStatus } from "@/lib/assistant-client";
import { useAuth } from "@/lib/auth";

interface NavItem {
  href: string;
  label: string;
}

interface NavSection {
  label: string;
  href: string;
  // Rutas que pertenecen a esta sección (para marcarla activa y mostrar su sub-navegación).
  children?: NavItem[];
}

// Agrupado por lo que la persona viene a hacer, no por cómo está construido el backend.
export const NAV_SECTIONS: NavSection[] = [
  { label: "Inicio", href: "/inicio" },
  { label: "Asistente", href: "/assistant" },
  {
    label: "Memoria",
    href: "/search",
    children: [
      { href: "/search", label: "Buscar" },
      { href: "/graph", label: "Grafo" },
      { href: "/timeline", label: "Línea de tiempo" },
      { href: "/capture", label: "Capturar" },
    ],
  },
  {
    label: "Pensamiento",
    href: "/explain",
    children: [
      { href: "/explain", label: "Razonamiento" },
      { href: "/cognitive", label: "Siete preguntas" },
      { href: "/contradictions", label: "Contradicciones" },
    ],
  },
  {
    label: "Agentes",
    href: "/routines",
    children: [
      { href: "/routines", label: "Rutinas" },
      { href: "/approvals", label: "Aprobaciones" },
    ],
  },
  { label: "Diagramas", href: "/diagrams" },
];

function matches(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function sectionFor(pathname: string): NavSection | undefined {
  return NAV_SECTIONS.find((s) =>
    s.children ? s.children.some((c) => matches(pathname, c.href)) : matches(pathname, s.href),
  );
}

/** Marca de MindOS: tres nodos enlazados, con el degradado reservado al logotipo. */
export function BrandLogo() {
  return (
    <Link href="/inicio" className="flex items-center gap-2 text-obsidian">
      <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
        <defs>
          <linearGradient id="mindos-mark" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#5b8def" />
            <stop offset="0.55" stopColor="#9b7bf7" />
            <stop offset="1" stopColor="#f59a62" />
          </linearGradient>
        </defs>
        <path d="M6 15.5 10 7.6M12 7.6l4 7.9M7.6 17h6.8" stroke="#000" strokeWidth="1.4" fill="none" />
        <circle cx="11" cy="5.5" r="3" fill="url(#mindos-mark)" />
        <circle cx="5" cy="17" r="2.6" fill="url(#mindos-mark)" />
        <circle cx="17" cy="17" r="2.6" fill="url(#mindos-mark)" />
      </svg>
      <span className="text-[19px] font-medium tracking-[-0.4px]">MindOS</span>
    </Link>
  );
}

/** Barra de aviso superior: solo aparece cuando el asistente corre en modo demostración. */
function DemoBar() {
  const [status, setStatus] = useState<AssistantStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAssistantStatus()
      .then((s) => !cancelled && setStatus(s))
      .catch(() => {
        // Sin servicio de agentes no hay nada fiable que anunciar; cada vista muestra su error.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (status?.provider !== "demo") return null;
  return (
    <div className="bg-obsidian px-5 py-2 text-center text-caption text-paper">
      Modo demostración: el asistente busca en tu memoria pero no razona hasta que configures{" "}
      <code className="font-mono text-mono">ANTHROPIC_API_KEY</code>.
    </div>
  );
}

export function TopNav() {
  const pathname = usePathname();
  const { username, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const current = sectionFor(pathname);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setIsOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen]);

  return (
    <>
      <DemoBar />
      <header
        className="sticky top-0 z-30 bg-paper"
        style={{ boxShadow: scrolled ? "var(--shadow-nav)" : undefined }}
      >
        <Container className="flex h-16 items-center justify-between gap-6">
          <BrandLogo />

          <nav aria-label="Principal" className="hidden lg:block">
            <ul className="flex items-center gap-1">
              {NAV_SECTIONS.map((section) => {
                const active = current === section;
                return (
                  <li key={section.label}>
                    <Link
                      href={section.href}
                      aria-current={active ? "page" : undefined}
                      className={`relative block px-3 py-2 text-body-sm ${
                        active ? "text-obsidian" : "text-slate hover:text-obsidian"
                      }`}
                    >
                      {section.label}
                      {active && (
                        <span aria-hidden="true" className="absolute inset-x-3 -bottom-[13px] h-0.5 bg-periwinkle" />
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="flex items-center gap-2">
            {/* Envueltos: `hidden` en el propio botón choca con su `inline-flex` y no se ocultaba. */}
            <div className="hidden items-center gap-2 sm:flex">
              <ButtonLink href="/capture" variant="ghost">
                Capturar
              </ButtonLink>
              <ButtonLink href="/assistant">Preguntar</ButtonLink>
            </div>
            <details className="relative hidden lg:block">
              <summary className="cursor-pointer list-none rounded-md px-2 py-2 font-mono text-mono text-slate hover:text-obsidian">
                {username}
              </summary>
              <div className="absolute right-0 mt-2 w-44 rounded-md border border-hairline bg-paper p-1">
                <button
                  onClick={logout}
                  className="w-full rounded-md px-3 py-2 text-left text-caption text-slate hover:bg-wash hover:text-obsidian"
                >
                  Cerrar sesión
                </button>
              </div>
            </details>
            <button
              onClick={() => setIsOpen(true)}
              aria-expanded={isOpen}
              aria-controls="mobile-nav"
              className="-mr-2 rounded-md p-2 text-obsidian lg:hidden"
            >
              <MenuIcon />
              <span className="sr-only">Abrir menú</span>
            </button>
          </div>
        </Container>

        {current?.children && (
          <div className="border-t border-hairline">
            <Container>
              <ul className="-mx-3 flex gap-1 overflow-x-auto">
                {current.children.map((item) => {
                  const active = matches(pathname, item.href);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={`relative block px-3 py-2.5 font-mono text-mono whitespace-nowrap ${
                          active ? "text-obsidian" : "text-slate hover:text-obsidian"
                        }`}
                      >
                        {item.label}
                        {active && <span aria-hidden="true" className="absolute inset-x-3 bottom-0 h-0.5 bg-periwinkle" />}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </Container>
          </div>
        )}
        <div className="border-b border-hairline" />
      </header>

      {isOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button aria-label="Cerrar menú" onClick={() => setIsOpen(false)} className="absolute inset-0 bg-midnight/40" />
          <nav
            id="mobile-nav"
            aria-label="Principal"
            className="absolute inset-y-0 right-0 flex w-80 max-w-[88vw] flex-col overflow-y-auto bg-paper"
          >
            <div className="flex h-16 items-center justify-between border-b border-hairline px-5">
              <BrandLogo />
              <button onClick={() => setIsOpen(false)} className="-mr-2 rounded-md p-2">
                <CloseIcon />
                <span className="sr-only">Cerrar menú</span>
              </button>
            </div>
            <ul className="flex-1 px-5 py-4">
              {NAV_SECTIONS.map((section) => (
                <li key={section.label} className="border-b border-hairline py-3 last:border-b-0">
                  <Link
                    href={section.href}
                    onClick={() => setIsOpen(false)}
                    className={`text-subheading font-medium ${current === section ? "text-obsidian" : "text-slate"}`}
                  >
                    {section.label}
                  </Link>
                  {section.children && (
                    <ul className="mt-2 space-y-1">
                      {section.children.map((item) => (
                        <li key={item.href}>
                          <Link
                            href={item.href}
                            onClick={() => setIsOpen(false)}
                            aria-current={matches(pathname, item.href) ? "page" : undefined}
                            className={`block py-1 font-mono text-mono ${
                              matches(pathname, item.href) ? "text-obsidian" : "text-slate"
                            }`}
                          >
                            {item.label}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
            <div className="flex items-center justify-between border-t border-hairline px-5 py-4">
              <span className="truncate font-mono text-mono text-slate">{username}</span>
              <button onClick={logout} className="font-mono text-mono text-slate underline">
                Cerrar sesión
              </button>
            </div>
          </nav>
        </div>
      )}
    </>
  );
}
