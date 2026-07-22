import { relationLabel } from "@/lib/object-type-style";
import type { ExplainEvidenceDto } from "@/lib/types";

import { ObjectTypeBadge } from "./ObjectTypeBadge";

export function EvidenceTree({ evidence, depth }: { evidence: ExplainEvidenceDto; depth: number }) {
  return (
    <li>
      <div className="rounded-md border border-zinc-200 p-2 text-sm dark:border-zinc-800">
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <ObjectTypeBadge objectType={evidence.object_type} />
          <span className="font-medium text-zinc-900 dark:text-zinc-50">{evidence.title}</span>
          <span className="text-xs text-zinc-400">{relationLabel(evidence.relation_type)}</span>
        </div>
        <p className="line-clamp-2 text-zinc-600 dark:text-zinc-400">{evidence.content}</p>
        <div className="mt-1 text-xs text-zinc-400">
          confianza {evidence.confidence.toFixed(2)} · importancia {evidence.importance.toFixed(2)}
          {evidence.source && ` · origen: ${evidence.source.kind}`}
        </div>
      </div>
      {evidence.supporting.length > 0 && depth < 6 && (
        <ul className="mt-2 space-y-2 border-l-2 border-zinc-200 pl-4 dark:border-zinc-800">
          {evidence.supporting.map((child, i) => (
            <EvidenceTree key={`${child.node_id}-${i}`} evidence={child} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}
