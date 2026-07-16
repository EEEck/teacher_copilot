"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

/**
 * Top-of-chat notice when review-only memory candidates were staged this
 * session. Dismissible; reappears if the staged count increases.
 */
export function StagedMemoryBanner({
  candidateCount,
}: {
  candidateCount: number;
}) {
  const [dismissed, setDismissed] = useState(false);
  const lastCountRef = useRef(candidateCount);

  useEffect(() => {
    if (candidateCount > lastCountRef.current) {
      setDismissed(false);
    }
    lastCountRef.current = candidateCount;
  }, [candidateCount]);

  if (candidateCount <= 0 || dismissed) return null;

  return (
    <div className="flex shrink-0 items-start gap-2 border-b border-border bg-muted px-4 py-2 text-xs text-muted-foreground">
      <p className="min-w-0 flex-1">
        {candidateCount} review-only memory candidate
        {candidateCount === 1 ? "" : "s"} staged this session. Wiki files are
        unchanged — review them in Memory Sweep when ready.
      </p>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Dismiss staged memory notice"
        className="shrink-0 text-base leading-none text-muted-foreground hover:text-foreground"
        onClick={() => setDismissed(true)}
      >
        ×
      </Button>
    </div>
  );
}
