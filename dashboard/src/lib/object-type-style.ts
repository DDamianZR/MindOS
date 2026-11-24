import type { Tone } from "@/components/ui";

// Dos familias, no un color por tipo: con veintidós tonos el grafo no se lee.
// Pensamiento (blush) son los nodos del razonamiento; todo lo demás es memoria (sky).
const THOUGHT_TYPES = new Set([
  "question",
  "hypothesis",
  "investigation",
  "evidence",
  "decision",
  "outcome",
  "learning",
  "fact",
  "insight",
]);

/**
 * Hex para Cytoscape, que no entiende las clases pastel.
 * Relleno de la familia, borde y texto en negro, arista en slate, selección en periwinkle.
 */
export const OBJECT_FAMILY_HEX = {
  memoria: "#c1dff9",
  pensamiento: "#fde3f6",
  border: "#000000",
  text: "#000000",
  edge: "#4d4d4d",
  selectedBorder: "#bdbbff",
} as const;

export function objectTypeTone(type: string | null | undefined): Tone {
  if (type && THOUGHT_TYPES.has(type)) return "pensamiento";
  return "memoria";
}

export function objectTypeColor(objectType: string | null | undefined): string {
  return objectTypeTone(objectType) === "pensamiento"
    ? OBJECT_FAMILY_HEX.pensamiento
    : OBJECT_FAMILY_HEX.memoria;
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
