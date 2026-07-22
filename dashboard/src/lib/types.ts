// Tipos que reflejan los DTOs de MindOS (schemas/mindos_schemas/api/v1/*.py). Mantenidos a
// mano en vez de generados: el Gateway no expone un OpenAPI unificado de los downstream.

// Mantenido en sync a mano con schemas/mindos_schemas/domain/object_type.py (ObjectType).
export type ObjectType =
  | "note" | "idea" | "document" | "conversation" | "concept" | "person" | "project"
  | "task" | "resource" | "technology" | "event" | "observation" | "experience"
  | "question" | "hypothesis" | "investigation" | "evidence" | "decision" | "outcome"
  | "learning" | "fact" | "insight";

// Mantenido en sync a mano con schemas/mindos_schemas/domain/relation_type.py (RelationType).
export type RelationType =
  | "PART_OF" | "RELATED_TO" | "DERIVED_FROM" | "SUPPORTS" | "CONTRADICTS" | "CAUSED_BY"
  | "DUPLICATE_OF" | "MENTIONS" | "ANSWERS" | "EVIDENCES" | "DECIDES" | "LEADS_TO" | "CUSTOM";

export interface SourceDto {
  id: string;
  kind: string;
  uri: string | null;
  raw_ref: string | null;
  captured_at: string;
  metadata: Record<string, unknown>;
}

export interface SearchResultItem {
  node_id: string;
  version: number;
  title: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
  object_type: ObjectType | null;
  confidence: number;
  importance: number;
  status: string;
}

export interface SearchKnowledgeResponse {
  query: string;
  results: SearchResultItem[];
}

export interface ContextFragment {
  citation_label: string;
  node_id: string;
  version: number;
  title: string;
  content: string;
  object_type: ObjectType | null;
  source_id: string | null;
  score: number;
  similarity: number;
  importance: number;
  confidence: number;
  recency: number;
  via_graph: boolean;
}

export interface ContextTimelineEntry {
  node_id: string;
  version: number;
  title: string;
  created_at: string;
}

export interface ContradictionScanResponse {
  nodes_checked: number;
  contradictions_detected: number;
}

export interface ContextBundle {
  query: string;
  fragments: ContextFragment[];
  timeline: ContextTimelineEntry[];
  relations_summary: string[];
}

export interface EvidenceItem {
  node_id: string | null;
  url: string | null;
  quote: string | null;
  weight: number;
}

export interface NodeVersionDto {
  version: number;
  title: string;
  content: string;
  author: string;
  created_at: string;
  parent_version_id: string | null;
  confidence: number;
  importance: number;
  status: string;
  evidence: EvidenceItem[];
  salience: number;
  tombstoned_at: string | null;
}

export interface GetNodeHistoryResponse {
  node_id: string;
  object_type: ObjectType;
  versions: NodeVersionDto[];
}

export interface VersionProvenanceDto {
  version: number;
  created_at: string;
  author: string;
  source: SourceDto | null;
}

export interface GetNodeProvenanceResponse {
  node_id: string;
  chain: VersionProvenanceDto[];
}

export interface TimeTravelRelationDto {
  source_id: string;
  target_id: string;
  relation_type: string;
}

export interface TimeTravelResponse {
  node_id: string;
  at: string;
  found: boolean;
  version: NodeVersionDto | null;
  relations: TimeTravelRelationDto[];
}

export interface NeighborEdgeDto {
  source_id: string;
  target_id: string;
  relation_type: string;
  metadata: Record<string, unknown>;
}

export interface GetNodeNeighborsResponse {
  node_id: string;
  depth: number;
  neighbors: NeighborEdgeDto[];
}

export interface ExplainEvidenceDto {
  node_id: string;
  title: string;
  content: string;
  object_type: string | null;
  relation_type: string;
  confidence: number;
  importance: number;
  source: SourceDto | null;
  supporting: ExplainEvidenceDto[];
}

export interface ReasoningStepDto {
  id: string;
  episode_id: string;
  step_index: number;
  kind: string;
  input: string | null;
  output: string | null;
  capability_name: string | null;
  approved: boolean | null;
  feedback: string | null;
  created_at: string;
  knowledge_refs: string[];
}

export interface ReasoningEpisodeDto {
  id: string;
  goal: string;
  correlation_id: string;
  agent: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  final_output: string | null;
  steps: ReasoningStepDto[];
}

export interface ExplainNodeResponse {
  node_id: string;
  title: string;
  content: string;
  object_type: string | null;
  supporting_evidence: ExplainEvidenceDto[];
  episodes: ReasoningEpisodeDto[];
}

export interface ExplainEpisodeResponse {
  episode: ReasoningEpisodeDto;
  narrative: string[];
}

// --- Cognitive Query API (las 7 preguntas, F2-T4) ---

export interface PastThinkingItem {
  node_id: string;
  title: string;
  content: string;
  version: number;
  object_type: string | null;
  similarity: number;
  as_of_created_at: string;
}
export interface PastThinkingResponse {
  topic: string;
  at: string;
  items: PastThinkingItem[];
}

export interface SimilarIdeaItem {
  node_id: string;
  title: string;
  content: string;
  object_type: string;
  similarity: number;
  created_at: string;
}
export interface SimilarIdeasResponse {
  node_id: string;
  items: SimilarIdeaItem[];
}

export interface DecisionItem {
  node_id: string;
  title: string;
  content: string;
  rationale: string | null;
  created_at: string;
  evidence_node_ids: string[];
  decides_node_ids: string[];
}
export interface DecisionsResponse {
  topic: string;
  decisions: DecisionItem[];
}

export interface SupportResponse {
  node_id: string;
  title: string;
  content: string;
  object_type: string | null;
  support: ExplainEvidenceDto[];
}

export interface ContradictionPair {
  node_a_id: string;
  node_a_title: string;
  node_b_id: string;
  node_b_title: string;
  rationale: string | null;
  confidence: number | null;
}
export interface ContradictionsResponse {
  topic: string;
  contradictions: ContradictionPair[];
}

export interface PatternBucket {
  period: string;
  object_type: string;
  count: number;
}
export interface PatternsResponse {
  buckets: PatternBucket[];
  total_nodes: number;
  most_common_type: string | null;
}

export interface RegisterDecisionResponse {
  node_id: string;
  version: number;
  title: string;
  rationale: string;
  created_at: string;
}

// --- Aprobaciones (F1-T8/F3-T1/F3-T7) ---

export interface ApprovalRequestDto {
  id: string;
  episode_id: string;
  step_id: number;
  capability_name: string;
  inputs: Record<string, unknown>;
  status: "pending" | "approved" | "rejected";
  reply_to: { provider: string; sender_id: string } | null;
  created_at: string;
  resolved_at: string | null;
  result_output: string | null;
}

export interface ResolveApprovalResponse {
  approval: ApprovalRequestDto;
  executed: boolean;
}

export interface ListApprovalsResponse {
  approvals: ApprovalRequestDto[];
}

// --- Captura (F3-T3, vía comms/inbound) ---

export interface InboundMessageResponse {
  status: string;
  message_id: string;
  provider: string;
}

// --- Auth (F3-T1) ---

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
}

// --- Salud agregada (F3-T1) ---

export interface HealthResponse {
  status: string;
  service: string;
  downstream: Record<string, string>;
}
