// Cifras de la portada. Memoria y agente se piden por separado: si uno falla, el otro sigue.
import { request } from "./api-client";

export interface CountItem {
  key: string;
  count: number;
}

/** `date` llega como YYYY-MM-DD (UTC). */
export interface ActivityDay {
  date: string;
  created: number;
  updated: number;
}

export interface RecentNode {
  node_id: string;
  title: string;
  object_type: string | null;
  version: number;
  created_at: string;
}

export interface MemoryStatsResponse {
  generated_at: string;
  nodes: number;
  archived_nodes: number;
  versions: number;
  relations: number;
  sources: number;
  contradictions: number;
  by_type: CountItem[];
  by_source: CountItem[];
  by_relation: CountItem[];
  activity: ActivityDay[];
  recent_thinking: RecentNode[];
}

export interface AssistantCountItem {
  key: string;
  count: number;
}

export interface AssistantUsageTotals {
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens: number;
  cache_creation_input_tokens: number;
}

/** `date` llega como YYYY-MM-DD (UTC). */
export interface AssistantDayCount {
  date: string;
  turns: number;
}

export interface AssistantStatsResponse {
  provider: "anthropic" | "demo";
  model: string;
  since: string;
  conversations: number;
  turns: number;
  failed_turns: number;
  tool_calls: AssistantCountItem[];
  usage: AssistantUsageTotals;
  cache_hit_ratio: number | null;
  estimated_cost_usd: number;
  avg_turn_seconds: number | null;
  turns_by_day: AssistantDayCount[];
}

export function getMemoryStats(): Promise<MemoryStatsResponse> {
  return request<MemoryStatsResponse>("/api/v1/memory/stats");
}

export function getAssistantStats(): Promise<AssistantStatsResponse> {
  return request<AssistantStatsResponse>("/api/v1/agents/assistant/stats");
}
