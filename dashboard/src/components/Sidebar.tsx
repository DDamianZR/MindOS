"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/search", label: "Búsqueda" },
  { href: "/graph", label: "Grafo" },
  { href: "/timeline", label: "Timeline" },
  { href: "/explain", label: "Razonamiento" },
  { href: "/cognitive", label: "7 preguntas" },
  { href: "/contradictions", label: "Contradicciones" },
  { href: "/approvals", label: "Aprobaciones" },
  { href: "/capture", label: "Captura rápida" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { username, logout } = useAuth();

  return (
    <nav className="flex w-56 shrink-0 flex-col border-r border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="px-4 py-4 text-lg font-semibold text-zinc-900 dark:text-zinc-50">MindOS</div>
      <ul className="flex-1 space-y-0.5 px-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={`block rounded-md px-3 py-2 text-sm ${
                  active
                    ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                    : "text-zinc-700 hover:bg-zinc-200 dark:text-zinc-300 dark:hover:bg-zinc-800"
                }`}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="border-t border-zinc-200 px-4 py-3 text-sm dark:border-zinc-800">
        <p className="mb-2 truncate text-zinc-500 dark:text-zinc-400">{username}</p>
        <button
          onClick={logout}
          className="text-sm font-medium text-zinc-700 hover:underline dark:text-zinc-300"
        >
          Cerrar sesión
        </button>
      </div>
    </nav>
  );
}
