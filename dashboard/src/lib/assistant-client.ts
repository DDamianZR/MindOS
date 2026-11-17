// Cliente del asistente personal (F7-T6). Igual que el resto de la Dashboard, habla solo con el
// Gateway. La respuesta del chat es un stream SSE sobre un POST autenticado, así que no sirve
// `EventSource` (no admite POST ni cabeceras): se lee el cuerpo con `fetch` y se parte a mano.
import { ApiError, GATEWAY_URL, getAuthToken } from "./api-client";

export interface AssistantSource {
  node_id: string;
  title: string;
  object_type: string | null;
  score: number | null;
}

export interface AssistantStatus {
  provider: "anthropic" | "demo";
  model: string;
  tools: string[];
}

export interface TranscriptToolUse {
  id: string;
  name: string;
  ok: boolean;
  summary: string;
  sources: AssistantSource[];
}

export interface TranscriptMessage {
  role: "user" | "assistant";
  text: string;
  tools: TranscriptToolUse[];
  stop_reason: string | null;
}

export interface AssistantConversation {
  conversation_id: string;
  started_at: string;
  messages: TranscriptMessage[];
}

export type AssistantEvent =
  | { type: "conversation"; conversation_id: string }
  | { type: "text"; text: string }
  | { type: "thinking"; text: string }
  | { type: "tool_start"; id: string; name: string; label: string; input: Record<string, unknown> }
  | { type: "tool_end"; id: string; name: string; ok: boolean; summary: string; sources: AssistantSource[] }
  | { type: "restart" }
  | { type: "done"; stop_reason: string; model: string; usage: Record<string, number> }
  | { type: "error"; message: string };

function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function readError(resp: Response): Promise<ApiError> {
  let detail = resp.statusText;
  try {
    detail = (await resp.json()).detail || detail;
  } catch {
    // el cuerpo del error no era JSON: se conserva el statusText
  }
  return new ApiError(resp.status, detail);
}

export async function getAssistantStatus(): Promise<AssistantStatus> {
  const resp = await fetch(`${GATEWAY_URL}/api/v1/agents/assistant/status`, { headers: authHeaders() });
  if (!resp.ok) throw await readError(resp);
  return resp.json();
}

export async function getConversation(conversationId: string): Promise<AssistantConversation> {
  const resp = await fetch(`${GATEWAY_URL}/api/v1/agents/assistant/conversations/${conversationId}`, {
    headers: authHeaders(),
  });
  if (!resp.ok) throw await readError(resp);
  return resp.json();
}

function parseEventBlock(block: string): AssistantEvent | null {
  let eventName = "";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!eventName || dataLines.length === 0) return null;
  try {
    return { ...JSON.parse(dataLines.join("\n")), type: eventName } as AssistantEvent;
  } catch {
    return null;
  }
}

/**
 * Envía un mensaje y entrega los eventos del turno conforme llegan. Termina cuando el servidor
 * cierra el stream; si la conexión se corta antes de un `done`/`error`, quien consume lo nota
 * porque el generador acaba sin haber entregado ninguno de los dos.
 */
export async function* streamChat(
  message: string,
  conversationId: string | null,
  signal: AbortSignal,
): AsyncGenerator<AssistantEvent> {
  const resp = await fetch(`${GATEWAY_URL}/api/v1/agents/assistant/chat`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  });
  if (!resp.ok || !resp.body) throw await readError(resp);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const event = parseEventBlock(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      if (event) yield event;
      boundary = buffer.indexOf("\n\n");
    }
  }
}

/** Nombre legible del modelo para mostrarlo bajo el campo de mensaje. */
export function describeModel(status: AssistantStatus | null): string {
  if (!status) return "";
  if (status.provider === "demo") return "Modo demostración: sin API key de Claude";
  const known: Record<string, string> = {
    "claude-sonnet-5-5": "Claude Sonnet 5.5",
    "claude-sonnet-5": "Claude Sonnet 5",
    "claude-opus-5-5": "Claude Opus 5.5",
    "claude-haiku-5-5": "Claude Haiku 5.5",
  };
  return known[status.model] ?? status.model;
}
