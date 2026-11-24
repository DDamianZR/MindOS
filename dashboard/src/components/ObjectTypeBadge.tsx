import { Badge } from "@/components/ui";
import { objectTypeTone } from "@/lib/object-type-style";

const TYPE_LABELS: Record<string, string> = {
  note: "nota",
  idea: "idea",
  document: "documento",
  conversation: "conversación",
  concept: "concepto",
  person: "persona",
  project: "proyecto",
  task: "tarea",
  resource: "recurso",
  technology: "tecnología",
  event: "evento",
  observation: "observación",
  experience: "experiencia",
  question: "pregunta",
  hypothesis: "hipótesis",
  investigation: "investigación",
  evidence: "evidencia",
  decision: "decisión",
  outcome: "resultado",
  learning: "aprendizaje",
  fact: "hecho",
  insight: "hallazgo",
};

export function ObjectTypeBadge({ objectType }: { objectType: string | null | undefined }) {
  const label = objectType ? (TYPE_LABELS[objectType] ?? objectType) : "sin tipo";
  return <Badge tone={objectTypeTone(objectType)}>{label}</Badge>;
}
