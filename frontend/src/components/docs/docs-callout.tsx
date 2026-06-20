import {
  AlertTriangle,
  ClipboardList,
  Info,
  Lightbulb,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type DocsCalloutType =
  | "note"
  | "tip"
  | "warning"
  | "important"
  | "blueprint";

const calloutStyles: Record<
  DocsCalloutType,
  { icon: LucideIcon; label: string; className: string }
> = {
  note: {
    icon: Info,
    label: "Note",
    className: "border-border bg-muted/45",
  },
  tip: {
    icon: Lightbulb,
    label: "Tip",
    className: "border-primary/20 bg-muted/45",
  },
  warning: {
    icon: AlertTriangle,
    label: "Warning",
    className: "border-destructive/25 bg-muted/45",
  },
  important: {
    icon: ShieldCheck,
    label: "Important",
    className: "border-primary/30 bg-muted",
  },
  blueprint: {
    icon: ClipboardList,
    label: "Blueprint",
    className: "border-dashed border-primary/35 bg-muted/45",
  },
};

export function DocsCallout({
  type,
  title,
  children,
  className,
}: {
  type: DocsCalloutType;
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const style = calloutStyles[type] ?? calloutStyles.note;
  const Icon = style.icon;

  return (
    <aside
      className={cn(
        "not-prose my-6 overflow-hidden rounded-lg border px-4 py-3.5 shadow-sm",
        style.className,
        className,
      )}
    >
      <div className="mb-2 flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-md border border-border/80 bg-background shadow-sm">
          <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
        </span>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">
          {title ?? style.label}
        </p>
      </div>
      <div className="space-y-2 text-sm leading-6 text-foreground [&_ol]:ml-5 [&_ol]:list-decimal [&_ol]:space-y-1.5 [&_p]:leading-6 [&_ul]:ml-5 [&_ul]:list-disc [&_ul]:space-y-1.5">
        {children}
      </div>
    </aside>
  );
}
