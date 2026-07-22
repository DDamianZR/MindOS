// Color por object_type, compartido entre Búsqueda/Grafo/Timeline (F4-T1) para que un mismo
// tipo se reconozca visualmente igual en toda la Dashboard.
const PALETTE: Record<string, string> = {
  note: "#64748b", idea: "#f59e0b", document: "#0ea5e9", conversation: "#14b8a6",
  concept: "#8b5cf6", person: "#ec4899", project: "#6366f1", task: "#22c55e",
  resource: "#84cc16", technology: "#06b6d4", event: "#f97316", observation: "#78716c",
  experience: "#d946ef",
  question: "#eab308", hypothesis: "#a855f7", investigation: "#3b82f6", evidence: "#10b981",
  decision: "#ef4444", outcome: "#059669", learning: "#2563eb", fact: "#16a34a", insight: "#db2777",
};
const FALLBACK_COLORS = ["#64748b", "#0ea5e9", "#8b5cf6", "#f59e0b", "#22c55e", "#ec4899"];

export function objectTypeColor(objectType: string | null | undefined): string {
  if (!objectType) return "#94a3b8";
  if (PALETTE[objectType]) return PALETTE[objectType];
  let hash = 0;
  for (let i = 0; i < objectType.length; i++) hash = (hash * 31 + objectType.charCodeAt(i)) >>> 0;
  return FALLBACK_COLORS[hash % FALLBACK_COLORS.length];
}

const RELATION_LABELS: Record<string, string> = {
  PART_OF: "parte de", RELATED_TO: "relacionado con", DERIVED_FROM: "derivado de",
  SUPPORTS: "respalda", CONTRADICTS: "contradice", CAUSED_BY: "causado por",
  DUPLICATE_OF: "duplicado de", MENTIONS: "menciona", ANSWERS: "responde a",
  EVIDENCES: "evidencia de", DECIDES: "decide", LEADS_TO: "lleva a", CUSTOM: "personalizada",
};

export function relationLabel(relationType: string): string {
  return RELATION_LABELS[relationType] ?? relationType.toLowerCase();
}
