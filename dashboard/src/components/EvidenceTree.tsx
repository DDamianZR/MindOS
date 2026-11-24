import { relationLabel } from "@/lib/object-type-style";
import type { ExplainEvidenceDto } from "@/lib/types";

import { Badge } from "./ui";
import { ObjectTypeBadge } from "./ObjectTypeBadge";

export function EvidenceTree({ evidence, depth }: { evidence: ExplainEvidenceDto; depth: number }) {
  return (
    <li className="border-l border-hairline pl-4">
      <div className="py-3">
        <div className="flex flex-wrap items-center gap-2">
          <ObjectTypeBadge objectType={evidence.object_type} />
          <span className="text-body-sm font-medium text-obsidian">{evidence.title}</span>
          <Badge>{relationLabel(evidence.relation_type)}</Badge>
        </div>
        {evidence.content && (
          <p className="mt-2 line-clamp-2 text-body-sm text-slate">{evidence.content}</p>
        )}
        <p className="mt-2 font-mono text-mono-sm text-muted">
          confianza {evidence.confidence.toFixed(2)} · importancia {evidence.importance.toFixed(2)}
          {evidence.source && ` · origen ${evidence.source.kind}`}
        </p>
      </div>
      {evidence.supporting.length > 0 && depth < 6 && (
        <ul className="space-y-1">
          {evidence.supporting.map((child, i) => (
            <EvidenceTree key={`${child.node_id}-${i}`} evidence={child} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}
