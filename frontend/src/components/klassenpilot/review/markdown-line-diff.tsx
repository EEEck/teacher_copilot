"use client";

import { computeMarkdownDiff, shortWikiPath, type DiffLine } from "@/lib/markdown-diff";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

function DiffLineRow({ line, lineNo }: { line: DiffLine; lineNo: number }) {
  return (
    <div
      className={cn(
        "flex font-mono text-xs leading-5",
        line.kind === "added" && "bg-[var(--diff-added-bg)]",
        line.kind === "removed" && "bg-[var(--diff-removed-bg)]",
      )}
    >
      <span className="w-10 shrink-0 select-none pr-2 text-right text-muted-foreground">
        {lineNo}
      </span>
      <span
        className={cn(
          "w-4 shrink-0 select-none",
          line.kind === "added" && "text-primary",
          line.kind === "removed" && "text-destructive",
        )}
      >
        {line.kind === "added" ? "+" : line.kind === "removed" ? "−" : " "}
      </span>
      <pre className="min-w-0 flex-1 whitespace-pre-wrap break-words py-0">
        {line.text || " "}
      </pre>
    </div>
  );
}

export function MarkdownLineDiff({
  path,
  before,
  after,
  className,
  onDismiss,
  dismissAriaLabel = "Close file and return to lesson diary",
}: {
  path: string;
  before: string;
  after: string;
  className?: string;
  onDismiss?: () => void;
  dismissAriaLabel?: string;
}) {
  const lines = computeMarkdownDiff(before, after);

  return (
    <div className={cn("flex min-h-0 flex-col", className)}>
      <div className="mb-2 flex items-center gap-2">
        <p
          className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground"
          title={path}
        >
          {shortWikiPath(path)}
        </p>
        {onDismiss ? (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={dismissAriaLabel}
            className="shrink-0 text-base leading-none text-muted-foreground hover:text-foreground"
            onClick={onDismiss}
          >
            ×
          </Button>
        ) : null}
      </div>
      <ScrollArea className="min-h-0 flex-1 rounded-md border border-border bg-card">
        <div className="min-h-[8rem]">
          {lines.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">No changes.</p>
          ) : (
            lines.map((line, i) => (
              <DiffLineRow key={`${i}-${line.kind}`} line={line} lineNo={i + 1} />
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
