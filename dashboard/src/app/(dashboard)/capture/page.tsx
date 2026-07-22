"use client";

import { useRef, useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, sendInbound } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";

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

export default function CapturePage() {
  const { username } = useAuth();
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fileNeedsCaption = file && mediaKindFor(file) === "document" && file.type !== "application/pdf";

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
      const resp = await sendInbound({ senderId: username ?? "dashboard-user", text, media });
      setSuccess(`Capturado (id ${resp.message_id.slice(0, 8)}…). Se procesará en segundo plano.`);
      setText("");
      setFile(null);
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
      </p>

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
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-zinc-600 dark:text-zinc-400"
        />
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
