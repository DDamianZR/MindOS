"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, sendInbound } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { enqueueCapture, flushQueuedCaptures, listQueuedCaptures } from "@/lib/offline-queue";

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve((reader.result as string).split(",")[1] ?? "");
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function mediaKindFor(file: File): "image" | "audio" | "document" {
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("audio/")) return "audio";
  return "document";
}

/** Recoge lo que el service worker (public/sw.js) dejó en cache al interceptar un share_target. */
async function pickUpSharedPayload(): Promise<{ text: string; file: File | null } | null> {
  if (typeof caches === "undefined") return null;
  const cache = await caches.open("mindos-share-target-v1");
  const payloadResp = await cache.match("/__share-payload");
  if (!payloadResp) return null;

  const payload: { title: string; text: string; url: string } = await payloadResp.json();
  const text = [payload.text, payload.title, payload.url].filter(Boolean).join(" ").trim();

  let file: File | null = null;
  const fileResp = await cache.match("/__share-file");
  if (fileResp) {
    const blob = await fileResp.blob();
    file = new File([blob], "compartido", { type: blob.type });
  }

  await cache.delete("/__share-payload");
  await cache.delete("/__share-file");
  return { text, file };
}

function CaptureForm() {
  const { username } = useAuth();
  const searchParams = useSearchParams();
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  // El <input type="file"> nativo no puede reflejar un archivo asignado por script (los
  // navegadores no permiten setear su .files) -- este flag, no una lectura de ref durante el
  // render, es lo que decide si hace falta la confirmación textual de "adjunto compartido".
  const [isSharedFile, setIsSharedFile] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // StrictMode (activo por defecto en dev) monta-desmonta-remonta cada componente para detectar
  // efectos no idempotentes, disparando este efecto dos veces. pickUpSharedPayload CONSUME la
  // entrada del cache (la borra) -- sin este guard, la primera pasada la borraría y aplicaría
  // el estado, pero la segunda pasada (tras el remount, con los `useState` ya reiniciados a su
  // valor inicial) encontraría el cache vacío y no reaplicaría nada, dejando el formulario vacío.
  const hasPickedUpShare = useRef(false);

  const fileNeedsCaption = file && mediaKindFor(file) === "document" && file.type !== "application/pdf";

  async function refreshPendingCount() {
    setPendingCount((await listQueuedCaptures()).length);
  }

  async function syncPending() {
    const { sent } = await flushQueuedCaptures();
    await refreshPendingCount();
    if (sent > 0) setSuccess(`Se sincronizaron ${sent} captura(s) pendiente(s).`);
  }

  useEffect(() => {
    if (searchParams.get("shared") === "1" && !hasPickedUpShare.current) {
      hasPickedUpShare.current = true;
      pickUpSharedPayload().then((shared) => {
        if (!shared) return;
        if (shared.text) setText(shared.text);
        if (shared.file) {
          setFile(shared.file);
          setIsSharedFile(true);
        }
        window.history.replaceState({}, "", "/capture");
      });
    }
    // Hidratación desde IndexedDB (sistema externo), igual que auth.tsx lee localStorage al montar.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshPendingCount();
    syncPending();
    window.addEventListener("online", syncPending);
    return () => window.removeEventListener("online", syncPending);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() && !file) return;
    setIsSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const media = file
        ? { base64: await fileToBase64(file), mimetype: file.type || "application/octet-stream", kind: mediaKindFor(file) }
        : undefined;
      const input = { senderId: username ?? "dashboard-user", text, media };
      try {
        const resp = await sendInbound(input);
        setSuccess(`Capturado (id ${resp.message_id.slice(0, 8)}…). Se procesará en segundo plano.`);
      } catch (err) {
        if (err instanceof ApiError) throw err; // el Gateway respondió: error real, no de red.
        await enqueueCapture(input); // fetch nunca completó: sin conexión, se guarda para reintentar.
        await refreshPendingCount();
        setSuccess("Sin conexión: la captura se guardó y se enviará sola en cuanto vuelva la red.");
      }
      setText("");
      setFile(null);
      setIsSharedFile(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "No se pudo capturar.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-4 text-xl font-semibold text-zinc-900 dark:text-zinc-50">Captura rápida</h1>
      <p className="mb-4 text-sm text-zinc-500 dark:text-zinc-400">
        Cualquier cosa que anotes aquí entra por el mismo camino que WhatsApp o la CLI: un evento de captura que el
        pipeline de ingestión procesa (OCR en imágenes/PDF, transcripción en audio) y guarda como Objeto Cognitivo.
        Instala esta página como app (PWA) para capturar sin conexión o compartir fotos desde otras apps.
      </p>

      {pendingCount > 0 && (
        <div className="mb-4 flex items-center justify-between rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
          <span>{pendingCount} captura(s) esperando conexión para sincronizar.</span>
          <button onClick={syncPending} className="font-medium underline">
            Reintentar ahora
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Escribe una nota…"
          rows={5}
          className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,audio/*,.pdf"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setIsSharedFile(false);
          }}
          className="block w-full text-sm text-zinc-600 dark:text-zinc-400"
        />
        {/* Un archivo recibido por share_target (F4-T3) no puede reflejarse en el <input>
            nativo -- los navegadores no permiten asignarle .files por script -- así que sin
            esto el usuario no tendría forma de saber que sí quedó adjunto. */}
        {file && isSharedFile && (
          <p className="text-xs text-zinc-500 dark:text-zinc-400">Adjunto compartido: {file.type || "archivo"}</p>
        )}
        {fileNeedsCaption && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            Este tipo de archivo no se transcribe automáticamente: añade una nota en el texto o quedará descartado si
            llega vacío.
          </p>
        )}

        <ErrorBanner message={error} />
        {success && (
          <p className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
            {success}
          </p>
        )}

        <button
          type="submit"
          disabled={isSubmitting || (!text.trim() && !file)}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {isSubmitting ? "Enviando…" : "Capturar"}
        </button>
      </form>
    </div>
  );
}

export default function CapturePage() {
  return (
    <Suspense>
      <CaptureForm />
    </Suspense>
  );
}
