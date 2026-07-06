"use client";

import {
  CheckIcon,
  ClockIcon,
  PlusIcon,
  Undo2Icon,
  XIcon,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { MemorySweepCandidate, MemorySweepDecision } from "@/lib/api";
import {
  SWEEP_SECTION_ORDER,
  SWEEP_SECTION_TITLES,
  sweepBriefRows,
  type SweepBriefRow,
} from "@/lib/sweep-brief";

const DECISION_LABELS: Record<string, string> = {
  apply: "will be added",
  reject: "not needed",
  snooze: "review later",
  already_covered: "already in memory",
  delete: "removed",
};

function BriefRow({
  row,
  decision,
  busy,
  expanded,
  onToggleDetail,
  onDecision,
  onClear,
  renderDetail,
}: {
  row: SweepBriefRow;
  decision: MemorySweepDecision | undefined;
  busy?: boolean;
  expanded: boolean;
  onToggleDetail: () => void;
  onDecision: (action: MemorySweepDecision["action"]) => void;
  onClear: () => void;
  renderDetail: (candidate: MemorySweepCandidate) => ReactNode;
}) {
  const candidate = row.candidate;
  const changed = row.section === "changed";
  return (
    <li className="rounded-md border border-border/60 bg-background px-3 py-2">
      <div className="flex items-start gap-2">
        <button
          type="button"
          onClick={onToggleDetail}
          className="min-w-0 flex-1 text-left"
          title="Show the detailed card"
        >
          <div className="flex flex-wrap items-center gap-x-2 text-sm">
            <span className="font-medium">{row.label}</span>
            {row.occasionCount > 1 && (
              <span className="text-xs text-muted-foreground">
                mentioned on {row.occasionCount} occasions
              </span>
            )}
            {decision && (
              <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary">
                {DECISION_LABELS[decision.action] ?? decision.action}
              </span>
            )}
          </div>
          {!changed && (
            <p className="mt-0.5 text-sm text-muted-foreground">{row.summary}</p>
          )}
          {changed && (
            <div className="mt-0.5 space-y-0.5 text-sm">
              <p className="text-muted-foreground line-through decoration-muted-foreground/60">
                {candidate.replaces_content || "(no previous note)"}
              </p>
              <p className="text-foreground">{candidate.content}</p>
            </div>
          )}
        </button>
        <div className="flex shrink-0 items-center gap-1 pt-0.5">
          {decision ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={onClear}
              disabled={busy}
            >
              <Undo2Icon className="size-3" /> undo
            </Button>
          ) : (
            <>
              {row.canApply ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon-sm"
                      aria-label="Add to memory"
                      onClick={() => onDecision("apply")}
                      disabled={busy}
                    >
                      <PlusIcon className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="top">Add to memory</TooltipContent>
                </Tooltip>
              ) : (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon-sm"
                      aria-label="Confirm already in memory"
                      onClick={() => onDecision("already_covered")}
                      disabled={busy}
                    >
                      <CheckIcon className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    Confirm: already in memory
                  </TooltipContent>
                </Tooltip>
              )}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    aria-label="Not needed"
                    onClick={() => onDecision("reject")}
                    disabled={busy}
                  >
                    <XIcon className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top">Not needed</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    aria-label="Review later"
                    onClick={() => onDecision("snooze")}
                    disabled={busy}
                  >
                    <ClockIcon className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-72">
                  Review later — returns when newer matching evidence arrives,
                  or after 7 days.
                </TooltipContent>
              </Tooltip>
            </>
          )}
          <button
            type="button"
            className="ml-1 text-xs text-muted-foreground hover:text-foreground"
            onClick={onToggleDetail}
            disabled={busy}
          >
            {expanded ? "hide" : "details"}
          </button>
        </div>
      </div>
      {expanded && <div className="mt-3">{renderDetail(candidate)}</div>}
    </li>
  );
}

/**
 * Teacher-first Memory Sweep triage: explicit asks pinned first, then
 * new / changed (old → new) / retired rows with three uniform actions and a
 * sticky submit bar. The full detail cards stay available per row and via
 * the page-level "detailed cards" toggle — this is presentation only; all
 * decision state lives in the page (docs/mem_v3, M1b).
 */
export function MemorySweepBrief({
  candidates,
  decisions,
  busy,
  onDecision,
  onClear,
  onBulk,
  onSubmit,
  renderDetail,
}: {
  candidates: MemorySweepCandidate[];
  decisions: Record<string, MemorySweepDecision>;
  busy?: boolean;
  onDecision: (
    candidate: MemorySweepCandidate,
    action: MemorySweepDecision["action"],
  ) => void;
  onClear: (candidate: MemorySweepCandidate) => void;
  onBulk: (
    candidates: MemorySweepCandidate[],
    action: MemorySweepDecision["action"],
  ) => void;
  onSubmit: () => void;
  renderDetail: (candidate: MemorySweepCandidate) => ReactNode;
}) {
  const rows = useMemo(() => sweepBriefRows(candidates), [candidates]);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const pendingCount = Object.keys(decisions).length;
  const applyable = candidates.filter((c) => c.can_apply);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {rows.length} suggestion{rows.length === 1 ? "" : "s"} to review —
          add, dismiss, or postpone each one, then submit.
        </p>
        <div className="flex flex-wrap gap-2 text-xs">
          {applyable.length > 0 && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onBulk(applyable, "apply")}
              disabled={busy}
            >
              <PlusIcon className="size-3" /> Add all ({applyable.length})
            </Button>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onBulk(candidates, "reject")}
            disabled={busy}
          >
            <XIcon className="size-3" /> None needed
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onBulk(candidates, "snooze")}
            disabled={busy}
          >
            <ClockIcon className="size-3" /> All later
          </Button>
        </div>
      </div>

      {SWEEP_SECTION_ORDER.map((section) => {
        const sectionRows = rows.filter((row) => row.section === section);
        if (sectionRows.length === 0) return null;
        return (
          <div key={section}>
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {SWEEP_SECTION_TITLES[section]}
            </div>
            <ul className="space-y-1.5">
              {sectionRows.map((row) => (
                <BriefRow
                  key={row.key}
                  row={row}
                  decision={decisions[row.key]}
                  busy={busy}
                  expanded={expandedKey === row.key}
                  onToggleDetail={() =>
                    setExpandedKey((prev) => (prev === row.key ? null : row.key))
                  }
                  onDecision={(action) => onDecision(row.candidate, action)}
                  onClear={() => onClear(row.candidate)}
                  renderDetail={renderDetail}
                />
              ))}
            </ul>
          </div>
        );
      })}

      <div className="sticky bottom-0 -mx-1 flex items-center justify-between gap-3 rounded-t-md border-t border-border bg-background/95 px-3 py-2 backdrop-blur">
        <span className="text-sm text-muted-foreground">
          {pendingCount} of {rows.length} decided
        </span>
        <Button
          type="button"
          onClick={onSubmit}
          disabled={busy || pendingCount === 0}
        >
          {busy ? "Submitting…" : `Submit ${pendingCount} decision(s)`}
        </Button>
      </div>
    </div>
  );
}
