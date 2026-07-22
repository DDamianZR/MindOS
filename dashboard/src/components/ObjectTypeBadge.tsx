import { objectTypeColor } from "@/lib/object-type-style";

export function ObjectTypeBadge({ objectType }: { objectType: string | null | undefined }) {
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium text-white"
      style={{ backgroundColor: objectTypeColor(objectType) }}
    >
      {objectType ?? "?"}
    </span>
  );
}
