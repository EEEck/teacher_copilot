import type { CompletenessChecklist } from "@/lib/api";
import { cn } from "@/lib/utils";

export function DiaryChecklist({
  checklist,
  compact = false,
  inline = false,
}: {
  checklist: CompletenessChecklist | null;
  compact?: boolean;
  inline?: boolean;
}) {
  const list = (
    <ul
      className={cn(
        "space-y-2 text-sm",
        compact && "space-y-1 text-xs",
        inline && "mt-4 space-y-1.5 text-sm",
      )}
    >
      {checklist?.items.map((item) => (
        <li key={item.field} className="flex items-center gap-2">
          <span className={item.complete ? "text-primary" : "text-muted-foreground"}>
            {item.complete ? "✓" : "○"}
          </span>
          <span className={item.complete ? "text-foreground" : "text-muted-foreground"}>
            {item.label}
          </span>
        </li>
      ))}
    </ul>
  );

  if (inline) {
    return (
      <div className="mt-6 rounded-lg border bg-muted/40 px-4 py-3">
        <p className="text-xs font-medium text-muted-foreground">Key sections to cover</p>
        {list}
      </div>
    );
  }

  if (compact) {
    return (
      <div>
        <p className="mb-2 text-xs font-medium text-muted-foreground">Sections</p>
        {list}
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="mb-3 text-base font-semibold">Diary checklist</p>
      {list}
    </div>
  );
}
