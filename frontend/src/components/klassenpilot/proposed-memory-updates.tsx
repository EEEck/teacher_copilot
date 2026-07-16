"use client";

/**
 * @deprecated Post-save preference / signal UI is disconnected (harmonize memory
 * review). Keep helpers for tests and v1.3 in-chat cards that will call
 * `/memory/apply`. Do not mount after plan save or memory commit.
 */

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

const APPLICABLE = new Set([
  "user.md",
  "teacher_profile.md",
  "copilot.md",
  "copilot_profile.md",
  "planning_brief.md",
  "teaching_patterns.md",
]);

const COPILOT_PROFILE_LABELS = new Set([
  "avoid",
  "copilot",
  "copilot profile",
  "copilot working agreement",
  "planning pattern",
  "planning patterns",
  "practice task",
  "practice tasks",
]);

const TEACHER_PROFILE_LABELS = new Set([
  "communication",
  "lesson style",
  "teacher",
  "teacher profile",
]);

function cleanTargetLabel(value: string): string {
  return value.trim().toLowerCase().replaceAll("_", " ").replace(/\s+/g, " ");
}

function canonicalMemoryTarget(target: string): string {
  const normalized = target.trim().toLowerCase();
  if (normalized === "user.md") return "teacher_profile.md";
  if (normalized === "copilot.md") return "copilot_profile.md";
  return normalized;
}

function normalizeApplyTarget(target: string): string {
  const canonical = canonicalMemoryTarget(target);
  if (APPLICABLE.has(canonical) || canonical.startsWith("wiki/subjects/")) {
    return canonical;
  }
  const label = cleanTargetLabel(target);
  if (TEACHER_PROFILE_LABELS.has(label)) return "teacher_profile.md";
  if (COPILOT_PROFILE_LABELS.has(label)) return "copilot_profile.md";
  return "copilot_profile.md";
}

export function toApplicableMemoryCandidate(c: MemoryCandidate): {
  candidate: MemoryCandidate;
  canApply: boolean;
  originalTarget: string;
} {
  const target = normalizeApplyTarget(c.target);
  return {
    candidate: { ...c, target },
    canApply: APPLICABLE.has(target) || target.startsWith("wiki/subjects/"),
    originalTarget: c.target,
  };
}

function isImmediateApplyCandidate(c: MemoryCandidate): boolean {
  return c.fast_lane === true;
}

export function splitPostSaveMemoryCandidates(candidates: MemoryCandidate[]): {
  immediate: MemoryCandidate[];
  signals: MemoryCandidate[];
} {
  const immediate: MemoryCandidate[] = [];
  const signals: MemoryCandidate[] = [];
  for (const candidate of candidates) {
    if (isImmediateApplyCandidate(candidate)) {
      immediate.push(candidate);
    } else {
      signals.push(candidate);
    }
  }
  return { immediate, signals };
}

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
  const normalizedCandidates = candidates.map(toApplicableMemoryCandidate);
  const [approved, setApproved] = useState<Record<number, boolean>>(() =>
    Object.fromEntries(
      normalizedCandidates.map((c, i) => [i, c.canApply]),
    ),
  );

  if (!candidates.length) return null;
  const approvedList = normalizedCandidates
    .filter((_, i) => approved[i])
    .map((c) => c.candidate);

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
          {normalizedCandidates.map(({ candidate: c, canApply, originalTarget }, i) => {
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
                    {originalTarget !== c.target && <span>from {originalTarget}</span>}
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

export function MemorySignalsReview({
  candidates,
  saving,
  onContinue,
}: {
  candidates: MemoryCandidate[];
  saving?: boolean;
  onContinue: (kept: MemoryCandidate[], removed: MemoryCandidate[]) => void;
}) {
  const [kept, setKept] = useState<Record<number, boolean>>(() =>
    Object.fromEntries(candidates.map((_, i) => [i, true])),
  );

  if (!candidates.length) return null;

  const keptList = candidates.filter((_, i) => kept[i]);
  const removedList = candidates.filter((_, i) => !kept[i]);

  return (
    <Card variant="highlight" size="sm">
      <CardHeader>
        <CardTitle>Memory signals captured</CardTitle>
        <CardDescription>
          These are saved as signals for Memory Sweep, not written to persistent
          class memory now. Uncheck anything that should not be kept for later
          review.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-2">
          {candidates.map((c, i) => (
            <li key={i} className="flex items-start gap-2">
              <input
                type="checkbox"
                className="mt-1"
                checked={!!kept[i]}
                disabled={saving}
                onChange={(e) =>
                  setKept((prev) => ({ ...prev, [i]: e.target.checked }))
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
                </div>
                <p className="text-sm">{c.candidate_update}</p>
                {c.evidence && (
                  <p className="text-xs text-muted-foreground">{c.evidence}</p>
                )}
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
      <CardFooter className="gap-3">
        <Button
          onClick={() => onContinue(keptList, removedList)}
          disabled={saving}
        >
          {saving
            ? "Saving…"
            : `Keep ${keptList.length} signal(s) and continue`}
        </Button>
      </CardFooter>
    </Card>
  );
}
