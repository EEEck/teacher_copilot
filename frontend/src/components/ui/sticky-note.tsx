"use client";

import type { ReactNode } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Dismissible amber “sticky note” help callout (Memory Sweep review help pattern).
 * Parent owns open state and unmounts after onDismiss.
 */
export function StickyNote({
  title,
  children,
  onDismiss,
  dismissAriaLabel = "Dismiss note",
  className,
}: {
  title: string;
  children: ReactNode;
  onDismiss: () => void;
  dismissAriaLabel?: string;
  className?: string;
}) {
  return (
    <Alert
      className={cn(
        "border-amber-200 bg-amber-50 text-amber-950",
        className,
      )}
    >
      <AlertDescription className="text-amber-950">
        <div className="flex gap-3">
          <div className="flex-1 space-y-1">
            <div className="text-sm font-semibold text-amber-950">{title}</div>
            <div className="text-sm text-amber-950 [&_a]:text-amber-950">
              {children}
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={dismissAriaLabel}
            className="shrink-0 text-base leading-none text-amber-900 hover:bg-amber-100/80 hover:text-amber-950"
            onClick={onDismiss}
          >
            ×
          </Button>
        </div>
      </AlertDescription>
    </Alert>
  );
}
