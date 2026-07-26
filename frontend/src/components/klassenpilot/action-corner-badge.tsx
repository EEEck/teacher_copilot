import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Corner chip on class-home Action CTAs (Sharpen due / plan·memory Draft).
 * Parent must be `relative`.
 */
export function ActionCornerBadge({
  children,
  tone = "attention",
  className,
}: {
  children: ReactNode;
  /** Amber nudge (due / draft) vs quiet neutral (generating / failed). */
  tone?: "attention" | "neutral";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "absolute -top-1.5 -right-1.5 max-w-[7.5rem] truncate rounded-md border px-1.5 py-0.5 text-[10px] font-medium leading-none shadow-sm",
        tone === "attention"
          ? "border-amber-200 bg-amber-50 text-amber-950"
          : "border-border bg-background text-foreground",
        className,
      )}
    >
      {children}
    </span>
  );
}
