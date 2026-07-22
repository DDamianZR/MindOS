"use client";

import { useEffect } from "react";

/** Registra public/sw.js (F4-T3): app shell offline + intercepción del share_target. */
export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.error("No se pudo registrar el service worker", err);
    });
  }, []);

  return null;
}
