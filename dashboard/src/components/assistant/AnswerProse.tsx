"use client";

import Link from "next/link";
import { memo, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { AssistantSource } from "@/lib/assistant-client";

const CITE_PREFIX = "#cita:";

function normalize(title: string): string {
  return title.trim().toLocaleLowerCase("es");
}

/**
 * El asistente cita la memoria con el título del nodo entre comillas angulares: «Título».
 * Antes de pasar por Markdown, cada cita se convierte en un enlace interno marcado con
 * `#cita:`; el componente `a` de abajo lo pinta con el resaltador y, si el título coincide con
 * una fuente de memoria de este turno, lo enlaza a la vista de razonamiento de ese nodo.
 * Una página web con el mismo título se queda como cita, sin enlace.
 */
function markCitations(text: string): string {
  return text.replace(/«([^»\n]{1,200})»/g, (_match, title: string) => {
    const label = title.replace(/([\[\]\\])/g, "\\$1");
    return `[«${label}»](${CITE_PREFIX}${encodeURIComponent(title)})`;
  });
}

function AnswerProseImpl({
  text,
  sources,
  isStreaming,
}: {
  text: string;
  sources: AssistantSource[];
  isStreaming: boolean;
}) {
  const sourceByTitle = useMemo(() => {
    const map = new Map<string, AssistantSource>();
    for (const source of sources) {
      const key = normalize(source.title);
      const previous = map.get(key);
      const memory = source.kind !== "web" && Boolean(source.node_id);
      const previousMemory = Boolean(previous && previous.kind !== "web" && previous.node_id);
      // Si el mismo título sale de la memoria y de la web, la cita enlaza a la memoria.
      if (!previous || (memory && !previousMemory)) map.set(key, source);
    }
    return map;
  }, [sources]);
  const marked = useMemo(() => markCitations(text), [text]);

  return (
    <div className={`answer ${isStreaming ? "answer-caret" : ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            if (href?.startsWith(CITE_PREFIX)) {
              const title = decodeURIComponent(href.slice(CITE_PREFIX.length));
              const source = sourceByTitle.get(normalize(title));
              if (!source || source.kind === "web" || !source.node_id) return <mark className="cite">{children}</mark>;
              return (
                <Link
                  href={`/explain?node_id=${source.node_id}`}
                  className="cite"
                  title="Ver de dónde sale esto"
                >
                  {children}
                </Link>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer noopener">
                {children}
              </a>
            );
          },
        }}
      >
        {marked}
      </ReactMarkdown>
    </div>
  );
}

// Un turno ya terminado no cambia: sin `memo`, cada token del turno en curso volvería a
// interpretar el Markdown de toda la conversación.
export const AnswerProse = memo(AnswerProseImpl);
