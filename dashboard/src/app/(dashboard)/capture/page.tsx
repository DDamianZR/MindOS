"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useId, useRef, useState, type FormEvent } from "react";

import { Button, ErrorNotice, PageHeader, Skeleton } from "@/components/ui";
import { ApiError, sendInbound } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { enqueueCapture, flushQueuedCaptures, listQueuedCaptures } from "@/lib/offline-queue";

const FIELD =
  "w-full rounded-md border border-hairline bg-paper px-3 py-2 text-body-sm text-obsidian placeholder:text-muted focus:border-obsidian";

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
  const textId = useId();
  const fileId = useId();
  const captionId = useId();
  const sharedId = useId();
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

  async function handleSubmit(e: FormEvent) {
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

  const fileDescribedBy =
    [file && isSharedFile ? sharedId : null, fileNeedsCaption ? captionId : null].filter(Boolean).join(" ") ||
    undefined;

  return (
    <div className="max-w-[40rem]">
      {pendingCount > 0 && (
        <div className="mb-6 flex flex-col items-start gap-3 rounded-md bg-mint px-4 py-3 sm:flex-row sm:items-center sm:justify-between" role="status">
          <p className="text-body-sm text-obsidian">{pendingCount} captura(s) esperando conexión para sincronizar.</p>
          <Button type="button" variant="ghost" onClick={syncPending}>
            Reintentar ahora
          </Button>
        </div>
      )}

      <form onSubmit={handleSubmit} method="post" className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor={textId} className="text-body-sm font-medium text-obsidian">
            Nota
          </label>
          <textarea
            id={textId}
            name="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Una idea, una cita, algo que no quieres olvidar"
            rows={5}
            className={FIELD}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor={fileId} className="text-body-sm font-medium text-obsidian">
            Archivo
          </label>
          <input
            ref={fileInputRef}
            id={fileId}
            name="file"
            type="file"
            accept="image/*,audio/*,.pdf"
            aria-describedby={fileDescribedBy}
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setIsSharedFile(false);
            }}
            className="block w-full max-w-full text-body-sm text-slate file:mr-3 file:h-10 file:rounded-md file:border-0 file:bg-obsidian file:px-4 file:font-mono file:text-mono file:font-medium file:uppercase file:text-paper"
          />
          {/* Un archivo recibido por share_target (F4-T3) no puede reflejarse en el <input>
              nativo -- los navegadores no permiten asignarle .files por script -- así que sin
              esto el usuario no tendría forma de saber que sí quedó adjunto. */}
          {file && isSharedFile && (
            <p id={sharedId} className="text-caption text-muted">
              Adjunto compartido: {file.type || "archivo"}
            </p>
          )}
          {fileNeedsCaption && (
            <p id={captionId} className="text-caption text-slate">
              Este tipo de archivo no se transcribe solo. Añade una nota en el texto. Si llega vacío, se descarta.
            </p>
          )}
        </div>

        {error && <ErrorNotice>{error} Revisa la conexión y vuelve a intentarlo.</ErrorNotice>}
        {success && (
          <p role="status" className="rounded-md bg-mint px-4 py-3 text-body-sm text-obsidian">
            {success}
          </p>
        )}

        <div>
          <Button type="submit" disabled={isSubmitting || (!text.trim() && !file)} className="h-10">
            {isSubmitting ? "Enviando…" : "Capturar"}
          </Button>
        </div>
      </form>
    </div>
  );
}

export default function CapturePage() {
  return (
    <div>
      <PageHeader
        title="Capturar"
        continuation="una idea, un archivo, una nota de voz"
        description="Escribe una nota o adjunta una foto, un PDF o un audio. Sin conexión, se envía cuando vuelva la red."
      />
      <Suspense
        fallback={
          <div className="relative max-w-[40rem] space-y-3" aria-busy="true">
            <p className="pointer-events-none absolute m-[-1px] h-px w-px overflow-hidden border-0 p-0 whitespace-nowrap [clip-path:inset(50%)]">
              Cargando el formulario
            </p>
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-10 w-40" />
          </div>
        }
      >
        <CaptureForm />
      </Suspense>
    </div>
  );
}
