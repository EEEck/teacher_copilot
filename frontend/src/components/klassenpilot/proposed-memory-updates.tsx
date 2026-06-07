"use client";

import { useState } from "react";
import type { MemoryCandidate } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const APPLICABLE = new Set(["user.md", "copilot.md", "class_state.md"]);

/**
 * Review surface for durable-memory updates the copilot proposed during a
 * planning session. Nothing is written until the teacher approves and applies
 * (HITL); canonical-wiki candidates are review-only here.
 */
export function ProposedMemoryUpdates({
  candidates,
  onApply,
  applying,
  onContinue,
  continueLabel = "Continue",
}: {
  candidates: MemoryCandidate[];
  onApply?: (approved: MemoryCandidate[]) => void;
  applying?: boolean;
  onContinue?: () => void;
  continueLabel?: string;
}) {
  const [approved, setApproved] = useState<Record<number, boolean>>(() =>
    Object.fromEntries(
      candidates.map((c, i) => [i, APPLICABLE.has(c.target)]),
    ),
  );

  if (!candidates.length) return null;
  const approvedList = candidates.filter((_, i) => approved[i]);

  return (
    <Card variant="highlight" size="sm">
      <CardHeader>
        <CardTitle>Proposed memory updates</CardTitle>
        <CardDescription>
          Suggestions captured during this session. Nothing is saved to class
          memory until you approve and apply.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-2">
          {candidates.map((c, i) => {
            const canApply = APPLICABLE.has(c.target);
            return (
              <li key={i} className="flex items-start gap-2">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={!!approved[i]}
                  disabled={!canApply || applying}
                  onChange={(e) =>
                    setApproved((prev) => ({ ...prev, [i]: e.target.checked }))
                  }
                />
                <div className="flex flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span className="rounded bg-accent px-1.5 py-0.5 font-medium text-accent-foreground">
                      {c.target}
                    </span>
                    {c.section && <span>{c.section}</span>}
                    {c.source && <span>{c.source}</span>}
                    {c.basis && <span>{c.basis}</span>}
                    {c.confidence && <span>· {c.confidence} confidence</span>}
                    {!canApply && <span>· review only</span>}
                  </div>
                  <p className="text-sm">{c.candidate_update}</p>
                  {c.evidence && (
                    <p className="text-xs text-muted-foreground">{c.evidence}</p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </CardContent>
      <CardFooter className="gap-3">
        {onApply && (
          <Button
            onClick={() => onApply(approvedList)}
            disabled={applying || approvedList.length === 0}
          >
            {applying ? "Applying…" : `Apply ${approvedList.length} update(s)`}
          </Button>
        )}
        {onContinue && (
          <Button variant="outline" onClick={onContinue} disabled={applying}>
            {continueLabel}
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
