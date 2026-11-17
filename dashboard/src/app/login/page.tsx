"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { BrandMark } from "@/components/icons";
import { ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";

const HOME = "/assistant";

function LoginForm() {
  const { login, isAuthenticated } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Navegar es un efecto, no parte del render: cubre tanto llegar aquí con sesión abierta como
  // el momento en que `login()` la crea.
  useEffect(() => {
    if (isAuthenticated) router.replace(searchParams.get("from") || HOME);
  }, [isAuthenticated, router, searchParams]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "No se pudo conectar con MindOS. Revisa que el Gateway esté en marcha.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  const inputClass =
    "mt-1.5 w-full rounded-lg border border-rule-strong bg-surface px-3 py-2.5 text-[0.9375rem] text-ink outline-none focus:border-accent";

  return (
    <div className="flex flex-1 items-center justify-center px-5 py-10">
      <div className="w-full max-w-[22rem]">
        <BrandMark width={28} height={28} className="text-accent" />
        <h1 className="mt-5 font-serif text-[2rem] leading-tight font-normal tracking-[-0.015em] text-ink">
          Tu memoria te estaba esperando
        </h1>
        <p className="mt-2 text-[0.9375rem] leading-relaxed text-ink-soft">
          Entra para conversar con lo que has guardado en MindOS.
        </p>

        <form onSubmit={handleSubmit} className="mt-8">
          <label className="block text-sm font-medium text-ink" htmlFor="username">
            Usuario
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              className={inputClass}
            />
          </label>

          <label className="mt-4 block text-sm font-medium text-ink" htmlFor="password">
            Contraseña
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className={inputClass}
            />
          </label>

          {error && (
            <p role="alert" className="mt-4 text-sm text-danger">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-6 w-full rounded-lg bg-accent px-3 py-2.5 text-[0.9375rem] font-medium text-accent-ink disabled:opacity-60"
          >
            {isSubmitting ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
