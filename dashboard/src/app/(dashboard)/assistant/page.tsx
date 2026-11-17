"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AnswerProse } from "@/components/assistant/AnswerProse";
import { Composer, type ComposerHandle } from "@/components/assistant/Composer";
import { Marginalia, type ToolRun, uniqueSources } from "@/components/assistant/Marginalia";
import { NewConversationIcon } from "@/components/icons";
import { ApiError } from "@/lib/api-client";
import {
  type AssistantEvent,
  type AssistantStatus,
  describeModel,
  getAssistantStatus,
  getConversation,
  streamChat,
} from "@/lib/assistant-client";

const CONVERSATION_KEY = "mindos_assistant_conversation";

interface Turn {
  id: string;
  question: string;
  answer: string;
  thinking: string;
  tools: ToolRun[];
  // streaming: llegando · done: completo · error: falló · stopped: lo detuvo la persona
  status: "streaming" | "done" | "error" | "stopped";
  notice: string | null;
}

// Comienzos de frase, no preguntas cerradas: cada persona los termina con su propio tema. Salen
// de lo que MindOS sabe responder (decisiones, pensamiento pasado, contradicciones, captura).
const STARTERS = [
  "¿Qué decidí sobre ",
  "¿Qué pensaba hace seis meses sobre ",
  "¿En qué me estoy contradiciendo cuando hablo de ",
  "Resume lo que sé sobre ",
  "Anota esto: ",
];

function newTurn(question: string): Turn {
  return {
    id: crypto.randomUUID(), question, answer: "", thinking: "", tools: [], status: "streaming", notice: null,
  };
}

function applyEvent(turn: Turn, event: AssistantEvent): Turn {
  switch (event.type) {
    case "text":
      return { ...turn, answer: turn.answer + event.text };
    case "thinking":
      return { ...turn, thinking: turn.thinking + event.text };
    case "tool_start":
      return {
        ...turn,
        tools: [...turn.tools, { id: event.id, name: event.name, label: event.label, status: "running", summary: "", sources: [] }],
      };
    case "tool_end":
      return {
        ...turn,
        tools: turn.tools.map((tool) =>
          tool.id === event.id
            ? { ...tool, status: event.ok ? "ok" : "error", summary: event.summary, sources: event.sources }
            : tool,
        ),
      };
    case "restart":
      // El servidor reintenta el turno: lo ya pintado de este intento se descarta.
      return { ...turn, answer: "", thinking: "" };
    case "done":
      return {
        ...turn,
        status: "done",
        notice: event.stop_reason === "max_tokens" ? "La respuesta se cortó por su longitud. Pide que continúe." : null,
      };
    case "error":
      return { ...turn, status: "error", notice: event.message };
    default:
      return turn;
  }
}

/** Lo que el asistente está haciendo ahora mismo, mientras todavía no hay texto que leer. */
function liveStatus(turn: Turn): string | null {
  if (turn.status !== "streaming") return null;
  const running = turn.tools.filter((t) => t.status === "running");
  if (running.length > 0) return running[running.length - 1].label;
  if (turn.answer) return null;
  return turn.thinking ? "Pensando" : "Leyendo tu mensaje";
}

function TurnView({ turn, onRetry }: { turn: Turn; onRetry: (() => void) | null }) {
  const status = liveStatus(turn);
  const sources = uniqueSources(turn.tools);
  const hasNotes = turn.tools.some((t) => t.status !== "running") || Boolean(turn.thinking);

  return (
    <article className="grid gap-x-12 border-t border-rule pt-7 pb-9 first:border-t-0 first:pt-0 lg:grid-cols-[minmax(0,40rem)_13.5rem]">
      <h2 className="text-[1.0625rem] leading-snug font-semibold whitespace-pre-wrap text-ink lg:col-start-1">
        {turn.question}
      </h2>

      <div className="mt-3 min-w-0 lg:col-start-1">
        {turn.answer && (
          <AnswerProse text={turn.answer} sources={sources} isStreaming={turn.status === "streaming" && !status} />
        )}

        {status && (
          <p role="status" className={`status-dots text-sm text-ink-faint ${turn.answer ? "mt-3" : ""}`}>
            {status}
          </p>
        )}

        {turn.notice && (
          <p className={`mt-3 text-sm ${turn.status === "error" ? "text-danger" : "text-ink-faint"}`}>
            {turn.notice}{" "}
            {onRetry && (
              <button onClick={onRetry} className="font-medium text-accent underline underline-offset-2">
                Volver a intentar
              </button>
            )}
          </p>
        )}

        {hasNotes && (
          <details className="mt-4 text-sm lg:hidden">
            <summary className="cursor-pointer text-ink-faint select-none">
              {sources.length > 0
                ? `Fuentes consultadas (${sources.length})`
                : "Qué consultó"}
            </summary>
            <div className="mt-3">
              <Marginalia tools={turn.tools} thinking={turn.thinking} />
            </div>
          </details>
        )}
      </div>

      {hasNotes && (
        <aside aria-label="Fuentes de esta respuesta" className="hidden lg:col-start-2 lg:row-start-2 lg:mt-3 lg:block">
          <Marginalia tools={turn.tools} thinking={turn.thinking} />
        </aside>
      )}
    </article>
  );
}

export default function AssistantPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  const conversationIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const composerRef = useRef<ComposerHandle>(null);

  // Al entrar: qué modelo hay detrás y, si quedó una conversación abierta en esta pestaña, restaurarla.
  useEffect(() => {
    let cancelled = false;

    getAssistantStatus()
      .then((status) => !cancelled && setAssistantStatus(status))
      .catch((err) => {
        if (cancelled) return;
        setStatusError(
          err instanceof ApiError && err.status < 500
            ? err.detail
            : "No se pudo contactar al servicio de agentes. Revisa que esté en marcha.",
        );
      });

    const saved = sessionStorage.getItem(CONVERSATION_KEY);
    if (saved) {
      getConversation(saved)
        .then((conversation) => {
          if (cancelled) return;
          conversationIdRef.current = conversation.conversation_id;
          const restored: Turn[] = [];
          for (const message of conversation.messages) {
            if (message.role === "user") {
              restored.push({ ...newTurn(message.text), status: "done" });
            } else if (restored.length > 0) {
              const last = restored[restored.length - 1];
              last.answer = message.text;
              last.tools = message.tools.map((tool) => ({
                id: tool.id, name: tool.name, label: tool.name, summary: tool.summary,
                status: tool.ok ? "ok" : "error", sources: tool.sources,
              }));
            }
          }
          setTurns(restored);
        })
        // La conversación ya no existe (el servicio se reinició): se empieza limpio, sin aviso.
        .catch(() => sessionStorage.removeItem(CONVERSATION_KEY));
    }

    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, []);

  // Sigue el final de la conversación mientras llega texto, salvo que la persona haya subido a releer.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottomRef.current) el.scrollTop = el.scrollHeight;
  }, [turns]);

  function handleScroll() {
    const el = scrollRef.current;
    if (!el) return;
    stickToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  const send = useCallback(async (text: string) => {
    const question = text.trim();
    if (!question) return;

    const turn = newTurn(question);
    const update = (fn: (t: Turn) => Turn) =>
      setTurns((current) => current.map((t) => (t.id === turn.id ? fn(t) : t)));

    setTurns((current) => [...current, turn]);
    setIsStreaming(true);
    stickToBottomRef.current = true;

    const controller = new AbortController();
    abortRef.current = controller;
    let closed = false;

    try {
      for await (const event of streamChat(question, conversationIdRef.current, controller.signal)) {
        if (event.type === "conversation") {
          conversationIdRef.current = event.conversation_id;
          sessionStorage.setItem(CONVERSATION_KEY, event.conversation_id);
          continue;
        }
        if (event.type === "done" || event.type === "error") closed = true;
        update((t) => applyEvent(t, event));
      }
      if (!closed) {
        update((t) => ({
          ...t, status: "error", notice: "La conexión se cortó antes de que terminara la respuesta.",
        }));
      }
    } catch (err) {
      if (controller.signal.aborted) {
        update((t) => ({
          ...t, status: "stopped", notice: "Respuesta detenida antes de terminar.",
        }));
      } else {
        if (err instanceof ApiError && err.status === 404) {
          // La conversación ya no existe en el servidor: el siguiente mensaje abre una nueva.
          conversationIdRef.current = null;
          sessionStorage.removeItem(CONVERSATION_KEY);
        }
        update((t) => ({
          ...t,
          status: "error",
          notice: err instanceof ApiError ? err.detail : "No se pudo conectar con MindOS. Revisa que el Gateway esté en marcha.",
        }));
      }
    } finally {
      abortRef.current = null;
      setIsStreaming(false);
    }
  }, []);

  function handleSend() {
    const text = draft;
    setDraft("");
    void send(text);
  }

  function handleRetry(turn: Turn) {
    setTurns((current) => current.filter((t) => t.id !== turn.id));
    void send(turn.question);
  }

  function startNewConversation() {
    conversationIdRef.current = null;
    sessionStorage.removeItem(CONVERSATION_KEY);
    setTurns([]);
    setDraft("");
    composerRef.current?.focusAtEnd();
  }

  function fillStarter(starter: string) {
    setDraft(starter);
    // El foco va después del render que pinta el texto, para que el cursor quede al final.
    requestAnimationFrame(() => composerRef.current?.focusAtEnd());
  }

  const isEmpty = turns.length === 0;
  const lastTurn = turns[turns.length - 1];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div ref={scrollRef} onScroll={handleScroll} className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[62rem] px-5 pt-6 md:px-10 md:pt-8">
          {!isEmpty && (
            <div className="mb-6 flex justify-end">
              <button
                onClick={startNewConversation}
                disabled={isStreaming}
                className="flex items-center gap-1.5 rounded-md px-2 py-1 text-sm text-ink-soft hover:bg-rule hover:text-ink disabled:opacity-50"
              >
                <NewConversationIcon />
                Conversación nueva
              </button>
            </div>
          )}

          {isEmpty ? (
            <section className="max-w-[40rem] pt-[8vh] pb-10 md:pt-[14vh]">
              <h1 className="font-serif text-[2.25rem] leading-[1.1] font-normal tracking-[-0.015em] text-ink md:text-[2.75rem]">
                ¿Qué quieres recordar?
              </h1>
              <p className="mt-4 max-w-[34rem] text-[0.9375rem] leading-relaxed text-ink-soft">
                Pregunta por algo que guardaste, pide conectar ideas que quedaron sueltas o dicta una
                nota. Cada respuesta muestra al margen de qué parte de tu memoria salió.
              </p>

              <p className="mt-10 mb-2 text-sm text-ink-faint">Empieza una frase y termínala con tu tema</p>
              <ul className="border-y border-rule">
                {STARTERS.map((starter) => (
                  <li key={starter} className="border-t border-rule first:border-t-0">
                    <button
                      onClick={() => fillStarter(starter)}
                      className="w-full py-2.5 text-left font-serif text-[1.125rem] text-ink-soft hover:text-ink"
                    >
                      {starter.trimEnd()}
                      <span className="text-ink-faint">{starter.trimEnd().endsWith(":") ? " …" : "…"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : (
            <div>
              {turns.map((turn) => (
                <TurnView
                  key={turn.id}
                  turn={turn}
                  onRetry={
                    turn === lastTurn && !isStreaming && (turn.status === "error" || turn.status === "stopped")
                      ? () => handleRetry(turn)
                      : null
                  }
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mx-auto w-full max-w-[62rem] px-5 pt-2 pb-4 md:px-10 md:pb-5">
        <div className="max-w-[40rem]">
          {statusError && <p className="mb-2 text-sm text-danger">{statusError}</p>}
          <Composer
            ref={composerRef}
            value={draft}
            onChange={setDraft}
            onSend={handleSend}
            onStop={() => abortRef.current?.abort()}
            isStreaming={isStreaming}
            footnote={describeModel(assistantStatus)}
          />
        </div>
      </div>
    </div>
  );
}
