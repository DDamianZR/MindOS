"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { TopNav } from "@/components/TopNav";
import { useAuth } from "@/lib/auth";

// Vistas que gestionan su propio ancho y alto: el Asistente (alto completo, scroll propio) y el
// Inicio (secciones a todo el ancho, incluida la banda oscura).
const FULL_BLEED_ROUTES = ["/assistant", "/inicio"];

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (isLoading || isAuthenticated) return;
    // Conserva a dónde iba (incluida la query -- p.ej. ?shared=1 del share_target de la PWA,
    // F4-T3) para volver ahí mismo después de loguearse.
    const query = searchParams.toString();
    const from = encodeURIComponent(query ? `${pathname}?${query}` : pathname);
    router.replace(`/login?from=${from}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) {
    return <div className="flex flex-1 items-center justify-center font-mono text-mono text-slate">Cargando…</div>;
  }

  const fullBleed = FULL_BLEED_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));
  const isAssistant = pathname.startsWith("/assistant");

  return (
    <div className={`flex flex-1 flex-col ${isAssistant ? "h-full min-h-0" : ""}`}>
      <TopNav />
      <main
        className={
          fullBleed
            ? `flex min-h-0 flex-1 flex-col ${isAssistant ? "" : ""}`
            : "mx-auto w-full max-w-[1200px] flex-1 px-5 pt-10 pb-20"
        }
      >
        {children}
      </main>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense>
      <AuthGuard>{children}</AuthGuard>
    </Suspense>
  );
}
