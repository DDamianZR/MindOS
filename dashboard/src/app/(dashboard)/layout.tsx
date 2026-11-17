"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { Sidebar } from "@/components/Sidebar";
import { useAuth } from "@/lib/auth";

// Vistas que gestionan su propio scroll y márgenes (ocupan todo el alto disponible).
const FULL_BLEED_ROUTES = ["/assistant"];

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (isLoading || isAuthenticated) return;
    // Conserva a dónde iba (incluida la query -- p.ej. ?shared=1 del share_target de la PWA,
    // F4-T3) para volver ahí mismo después de loguearse, en vez de perderlo en la vista inicial.
    const query = searchParams.toString();
    const from = encodeURIComponent(query ? `${pathname}?${query}` : pathname);
    router.replace(`/login?from=${from}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) {
    return <div className="flex flex-1 items-center justify-center text-sm text-ink-faint">Cargando…</div>;
  }

  const fullBleed = FULL_BLEED_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));

  return (
    <div className="flex min-h-0 flex-1 flex-col md:flex-row">
      <Sidebar />
      <main className={`min-h-0 min-w-0 flex-1 ${fullBleed ? "flex flex-col" : "overflow-y-auto p-4 md:p-8"}`}>
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
