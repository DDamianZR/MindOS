"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

import { SendIcon, StopIcon } from "@/components/icons";
import { Button } from "@/components/ui";

export interface ComposerHandle {
  /** Pone el foco en el campo y deja el cursor al final (para los comienzos de frase sugeridos). */
  focusAtEnd: () => void;
}

interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  isStreaming: boolean;
  footnote: string;
}

const MAX_HEIGHT_PX = 220;

export const Composer = forwardRef<ComposerHandle, ComposerProps>(function Composer(
  { value, onChange, onSend, onStop, isStreaming, footnote },
  ref,
) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    focusAtEnd() {
      const el = textareaRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    },
  }));

  // El campo crece con el texto hasta un tope y después hace scroll dentro de sí mismo.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [value]);

  const canSend = value.trim().length > 0 && !isStreaming;

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter envía; Mayús+Enter es salto de línea. Durante la composición de un IME (acentos
    // muertos, teclados asiáticos) Enter confirma el carácter y no debe enviar.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (canSend) onSend();
    }
  }

  return (
    <div>
      <div className="flex items-end gap-2 rounded-md border border-hairline bg-paper py-2 pr-2 pl-3 focus-within:border-obsidian">
        <label htmlFor="assistant-message" className="sr-only">
          Mensaje para el asistente
        </label>
        <textarea
          id="assistant-message"
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Pregunta a tu memoria o dicta una nota"
          className="min-h-9 flex-1 resize-none bg-transparent py-1.5 text-body-sm text-obsidian outline-none placeholder:text-muted focus-visible:outline-none"
        />
        {isStreaming ? (
          <Button type="button" variant="ghost" onClick={onStop} className="shrink-0">
            <StopIcon />
            Detener
          </Button>
        ) : (
          <button
            type="button"
            onClick={onSend}
            disabled={!canSend}
            className="flex size-9 shrink-0 items-center justify-center rounded-md bg-obsidian text-paper disabled:opacity-40"
          >
            <SendIcon />
            <span className="sr-only">Enviar</span>
          </button>
        )}
      </div>
      <p className="mt-2 flex flex-wrap justify-between gap-x-4 px-1 font-mono text-mono-sm text-muted">
        <span>{footnote}</span>
        <span className="hidden sm:inline">Enter envía, Mayús + Enter hace un salto de línea</span>
      </p>
    </div>
  );
});
