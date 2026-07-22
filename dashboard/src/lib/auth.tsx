"use client";

// AuthProvider (F4-T1): JWT de sesión emitido por el Gateway (`/api/v1/auth/login`), guardado en
// localStorage. Next.js 16 renombró "Middleware" a "Proxy" pero sigue sin ser una solución de
// auth/sesión completa (doc oficial) -- por eso el guard vive aquí, en un Client Component, y no
// en el server.
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import * as api from "./api-client";
import { setAuthToken } from "./api-client";

const STORAGE_KEY = "mindos_session";

interface StoredSession {
  token: string;
  username: string;
}

interface AuthContextValue {
  username: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        const parsed: StoredSession = JSON.parse(raw);
        // Hidratación desde localStorage (sistema externo): no hay valor a calcular durante
        // el render, solo leerlo.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSession(parsed);
        setAuthToken(parsed.token);
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const resp = await api.login(username, password);
    const next: StoredSession = { token: resp.access_token, username };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setAuthToken(next.token);
    setSession(next);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setAuthToken(null);
    setSession(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        username: session?.username ?? null,
        isAuthenticated: session !== null,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
