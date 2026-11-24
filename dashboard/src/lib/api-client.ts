// Cliente HTTP hacia el Gateway (F4-T1): la Dashboard consume SOLO el Gateway, nunca un
// servicio interno directo -- mismo principio que el servidor MCP (F4-T2).
import type {
  ContextBundle,
  ContradictionScanResponse,
  ContradictionsResponse,
  DecisionsResponse,
  ExplainEpisodeResponse,
  ExplainNodeResponse,
  GetNodeHistoryResponse,
  GetNodeNeighborsResponse,
  GetNodeProvenanceResponse,
  InboundMessageResponse,
  ListApprovalsResponse,
  LoginResponse,
  PastThinkingResponse,
  PatternsResponse,
  ResolveApprovalResponse,
  SearchKnowledgeResponse,
  SimilarIdeasResponse,
  SupportResponse,
  TimeTravelResponse,
} from "./types";

export const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

let authToken: string | null = null;

/** Llamado por AuthProvider al hidratar/cambiar sesión -- evita que este módulo dependa de React. */
export function setAuthToken(token: string | null) {
  authToken = token;
}

/** Para clientes que no pueden pasar por `request()` (el stream del asistente, F7-T6). */
export function getAuthToken(): string | null {
  return authToken;
}

export async function request<T>(
  path: string,
  options: { method?: string; params?: Record<string, string | number | boolean | undefined>; body?: unknown } = {},
): Promise<T> {
  const { method = "GET", params, body } = options;

  const url = new URL(`${GATEWAY_URL}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }

  const headers: Record<string, string> = {};
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const resp = await fetch(url.toString(), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const errJson = await resp.json();
      detail = errJson.detail || detail;
    } catch {
      // el body de error no era JSON, se conserva el statusText
    }
    throw new ApiError(resp.status, detail);
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

// --- Auth ---

export function login(username: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/api/v1/auth/login", { method: "POST", body: { username, password } });
}

// --- Memory: búsqueda, contexto, grafo, tiempo ---

export function search(query: string, limit = 5, includeArchived = false): Promise<SearchKnowledgeResponse> {
  return request<SearchKnowledgeResponse>("/api/v1/memory/search", {
    method: "POST",
    params: { query, limit, include_archived: includeArchived },
  });
}

export function getContext(query: string, limit = 5, depth = 1): Promise<ContextBundle> {
  return request<ContextBundle>("/api/v1/memory/context", { method: "POST", body: { query, limit, depth } });
}

export function getNodeHistory(nodeId: string): Promise<GetNodeHistoryResponse> {
  return request<GetNodeHistoryResponse>(`/api/v1/memory/node/${nodeId}/history`);
}

export function getNodeProvenance(nodeId: string): Promise<GetNodeProvenanceResponse> {
  return request<GetNodeProvenanceResponse>(`/api/v1/memory/node/${nodeId}/provenance`);
}

export function getNodeNeighbors(nodeId: string, depth = 2): Promise<GetNodeNeighborsResponse> {
  return request<GetNodeNeighborsResponse>(`/api/v1/memory/node/${nodeId}/neighbors`, { params: { depth } });
}

export function timeTravel(nodeId: string, at: string, maxDepth = 1): Promise<TimeTravelResponse> {
  return request<TimeTravelResponse>("/api/v1/memory/timetravel", {
    params: { node_id: nodeId, at, max_depth: maxDepth },
  });
}

export function scanContradictions(limit = 200): Promise<ContradictionScanResponse> {
  return request<ContradictionScanResponse>("/api/v1/memory/contradictions/scan", { method: "POST", params: { limit } });
}

// --- Thinking Graph: explicabilidad ---

export function explainNode(nodeId: string, maxDepth = 3): Promise<ExplainNodeResponse> {
  return request<ExplainNodeResponse>(`/api/v1/thinking/explain/${nodeId}`, { params: { max_depth: maxDepth } });
}

export function explainEpisode(episodeId: string): Promise<ExplainEpisodeResponse> {
  return request<ExplainEpisodeResponse>(`/api/v1/thinking/explain/episode/${episodeId}`);
}

// --- Cognitive Query API: las 7 preguntas ---

export function pastThinking(topic: string, at: string, limit = 5): Promise<PastThinkingResponse> {
  return request<PastThinkingResponse>("/api/v1/cognitive/past-thinking", { params: { topic, at, limit } });
}

export function similarIdeas(nodeId: string, limit = 5): Promise<SimilarIdeasResponse> {
  return request<SimilarIdeasResponse>("/api/v1/cognitive/similar", { params: { node_id: nodeId, limit } });
}

export function decisions(topic: string, limit = 5): Promise<DecisionsResponse> {
  return request<DecisionsResponse>("/api/v1/cognitive/decisions", { params: { topic, limit } });
}

export function support(nodeId: string, maxDepth = 3): Promise<SupportResponse> {
  return request<SupportResponse>("/api/v1/cognitive/support", { params: { node_id: nodeId, max_depth: maxDepth } });
}

export function contradictionsByTopic(topic: string, limit = 10): Promise<ContradictionsResponse> {
  return request<ContradictionsResponse>("/api/v1/cognitive/contradictions", { params: { topic, limit } });
}

export function patterns(limit = 500): Promise<PatternsResponse> {
  return request<PatternsResponse>("/api/v1/cognitive/patterns", { params: { limit } });
}

// --- Aprobaciones ---

export function listPendingApprovals(): Promise<ListApprovalsResponse> {
  // Trailing slash a propósito: es la ruta exacta que reconstruye el proxy del Gateway para
  // rest_of_path="" -- sin ella, Starlette del lado de Agents respondería 307 y el Gateway
  // (httpx sin follow_redirects) lo devolvería tal cual, rompiendo el fetch del navegador.
  return request<ListApprovalsResponse>("/api/v1/approvals/");
}

export function resolveApproval(approvalId: string, approved: boolean, resolvedBy?: string): Promise<ResolveApprovalResponse> {
  return request<ResolveApprovalResponse>(`/api/v1/approvals/${approvalId}/resolve`, {
    method: "POST",
    body: { approved, resolved_by: resolvedBy },
  });
}

// --- Captura (F3-T3, vía comms/inbound) ---

export interface InboundMessageInput {
  senderId: string;
  text: string;
  media?: { base64: string; mimetype: string; kind: "image" | "audio" | "document" };
}

export function sendInbound({ senderId, text, media }: InboundMessageInput): Promise<InboundMessageResponse> {
  return request<InboundMessageResponse>("/api/v1/comms/inbound", {
    method: "POST",
    body: {
      provider: "dashboard",
      sender_id: senderId,
      recipient_id: "mindos",
      text,
      metadata: media ? { media_kind: media.kind, mimetype: media.mimetype, media_base64: media.base64 } : {},
    },
  });
}
