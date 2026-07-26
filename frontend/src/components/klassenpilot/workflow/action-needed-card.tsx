"use client";

import { useEffect, useRef } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function focusComposerInput(): void {
  if (typeof document === "undefined") return;
  const input = document.querySelector<HTMLElement>(
    '.aui-composer-input, [aria-label="Message input"]',
  );
  input?.focus();
  input?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/**
 * In-chat red activity for workflow “action needed” errors (executive write-gate).
 * Pair with `classifyWorkflowError` / `routeWorkflowError` from `@/lib/workflow-error`.
 * System errors stay on the page banner (`ArtifactSessionPage` Alert) — not this card.
 */
export function WorkflowActionNeededCard({
  message,
  title = "Couldn't save yet",
  respondInChat = true,
  className,
}: {
  message: string;
  title?: string;
  respondInChat?: boolean;
  className?: string;
}) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    rootRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [message]);

  return (
    <Alert
      ref={rootRef}
      role="alert"
      className={cn(
        "border-destructive/30 bg-[var(--error-bg)] text-destructive shadow-sm",
        className,
      )}
    >
      <AlertDescription className="text-destructive">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
          <div className="min-w-0 space-y-1">
            <div className="text-sm font-semibold">{title}</div>
            <p className="whitespace-pre-line text-sm text-destructive/95">
              {message}
            </p>
          </div>
          {respondInChat ? (
            <Button
              type="button"
              variant="outline"
              size="default"
              className="shrink-0 border-destructive/40 bg-background text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={focusComposerInput}
            >
              Respond in chat
            </Button>
          ) : null}
        </div>
      </AlertDescription>
    </Alert>
  );
}
