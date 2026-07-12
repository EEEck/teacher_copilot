"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2Icon } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import {
  MemorySweepBrief,
  MemorySweepBulkToolbar,
} from "@/components/klassenpilot/memory-sweep-brief";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  client,
  type MemorySweepCandidate,
  type MemorySweepDecision,
  type MemorySweepProposalResponse,
  type MemorySweepReviewResponse,
} from "@/lib/api";
import {
  memorySweepLoadingSavedText,
  memorySweepProgressText,
} from "@/lib/memory-sweep-review-status";
import {
  clearPendingMemorySweep,
  markPendingMemorySweep,
} from "@/lib/pending-chat-turns";

const REVIEW_LATER_TOOLTIP =
  "Hide while the system waits for more evidence. It returns when newer matching evidence arrives, or after 7 days if it still needs review.";

function canApply(candidate: MemorySweepCandidate): boolean {
  return Boolean(candidate.can_apply);
}

function cardKey(candidate: MemorySweepCandidate): string {
  return candidate.card_id || candidate.candidate_id;
}

function cardDomId(candidate: MemorySweepCandidate): string {
  return `memory-sweep-card-${cardKey(candidate).replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function representedCandidateIds(candidate: MemorySweepCandidate): string[] {
  return candidate.candidate_ids?.length
    ? candidate.candidate_ids
    : [candidate.candidate_id];
}

function countCandidates(proposal: MemorySweepProposalResponse | null): number {
  if (!proposal) return 0;
  return Object.values(proposal.queues).reduce((sum, queue) => sum + queue.length, 0);
}

function warningCardLinks(proposal: MemorySweepProposalResponse | null): {
  warning: string;
  card: MemorySweepCandidate;
}[] {
  if (!proposal) return [];
  const items: { warning: string; card: MemorySweepCandidate }[] = [];
  const seen = new Set<string>();
  for (const candidates of Object.values(proposal.queues)) {
    for (const candidate of candidates) {
      for (const warning of candidate.warnings ?? []) {
        const key = `${cardKey(candidate)}:${warning}`;
        if (seen.has(key)) continue;
        seen.add(key);
        items.push({ warning, card: candidate });
      }
    }
  }
  return items;
}

function proposalFromReview(review: MemorySweepReviewResponse): MemorySweepProposalResponse {
  return {
    class_id: review.class_id,
    subject: "",
    queues: review.queues ?? {},
    warnings: review.warnings ?? [],
  };
}

function decisionsByCardFromList(
  decisions: MemorySweepDecision[],
): Record<string, MemorySweepDecision> {
  const keyed: Record<string, MemorySweepDecision> = {};
  for (const decision of decisions) {
    const key = decision.card_id || decision.candidate_ids[0];
    if (key) keyed[key] = decision;
  }
  return keyed;
}

function uniqueWarningCount(
  items: { warning: string; card: MemorySweepCandidate }[],
): number {
  return new Set(items.map((item) => item.warning)).size;
}

function buildDecision(
  candidate: MemorySweepCandidate,
  action: MemorySweepDecision["action"],
  content: string,
): MemorySweepDecision {
  return {
    card_id: candidate.card_id,
    action,
    target: candidate.target,
    section: candidate.section,
    content: action === "apply" ? content : "",
    operation: candidate.operation ?? "add",
    replaces_content: candidate.replaces_content ?? "",
    candidate_ids: representedCandidateIds(candidate),
    rejection_reason: action === "reject" ? "Rejected in sweep" : null,
  };
}

function CandidateCard({
  candidate,
  draft,
  decision,
  busy,
  onDraftChange,
  onDecision,
  onClear,
}: {
  candidate: MemorySweepCandidate;
  draft: string;
  decision: MemorySweepDecision | undefined;
  busy: boolean;
  onDraftChange: (value: string) => void;
  onDecision: (action: MemorySweepDecision["action"]) => void;
  onClear: () => void;
}) {
  const applicable = canApply(candidate);
  return (
    <Card id={cardDomId(candidate)} className="scroll-mt-6">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{candidate.target}</CardTitle>
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          <span>{candidate.section}</span>
          <span>{candidate.channel}</span>
          <span>{candidate.basis}</span>
          <span>{candidate.confidence} confidence</span>
          <span>{candidate.operation ?? "add"}</span>
          {candidate.group_label && <span>{candidate.group_label}</span>}
          <span>{candidate.status_recommendation}</span>
          {(candidate.occasion_count ?? 1) > 1 && (
            <span>{candidate.occasion_count} occasions</span>
          )}
          {!applicable && (
            <span>{candidate.review_only_reason || "review only"}</span>
          )}
          {decision && <span>selected: {decision.action}</span>}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {applicable ? (
          <div className="space-y-3">
            {(candidate.operation ?? "add") === "adjust" && (
              <div className="rounded border bg-muted/40 p-3 text-xs">
                <div className="mb-1 font-medium text-foreground">Replace</div>
                <p className="whitespace-pre-wrap text-muted-foreground">
                  {candidate.replaces_content || "Missing replacement source"}
                </p>
                <div className="mb-1 mt-3 font-medium text-foreground">With</div>
              </div>
            )}
            <Textarea
              value={draft}
              onChange={(e) => onDraftChange(e.target.value)}
              disabled={busy}
              className="min-h-24 text-sm"
            />
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-sm">{candidate.content}</p>
            <p className="text-xs text-muted-foreground">
              This suggestion cannot be added automatically. Choose whether it
              is already in memory, not needed, should be reviewed later while
              more evidence accumulates, or should be removed from the review
              list.
            </p>
          </div>
        )}
        {candidate.evidence_summary && (
          <p className="text-xs text-muted-foreground">
            {candidate.evidence_summary}
          </p>
        )}
        {candidate.why_now && (
          <p className="text-xs text-muted-foreground">
            Why now: {candidate.why_now}
          </p>
        )}
        {(candidate.warnings ?? []).map((warning) => (
          <Alert key={warning} className="border-border bg-muted">
            <AlertDescription>
              <div className="space-y-1">
                <div className="text-xs font-semibold text-foreground">
                  Warning
                </div>
                <p>{warning}</p>
              </div>
            </AlertDescription>
          </Alert>
        ))}
        {candidate.public_rationale && (
          <p className="text-xs text-muted-foreground">
            Rationale: {candidate.public_rationale}
          </p>
        )}
        {candidate.current_memory_excerpt && (
          <div className="rounded border bg-muted/40 p-3 text-xs text-muted-foreground">
            <div className="mb-1 font-medium text-foreground">
              Current memory excerpt
            </div>
            <p className="whitespace-pre-wrap">
              {candidate.current_memory_excerpt}
            </p>
          </div>
        )}
        {candidate.evidence_refs.length > 0 && (
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            {candidate.evidence_refs.map((ref) => (
              <span key={ref} className="rounded bg-muted px-2 py-1">
                {ref}
              </span>
            ))}
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          {applicable && (
            <Button onClick={() => onDecision("apply")} disabled={busy}>
              {(candidate.operation ?? "add") === "adjust"
                ? "Apply adjustment"
                : "Add memory"}
            </Button>
          )}
          <Button
            variant="outline"
            onClick={() => onDecision("already_covered")}
            disabled={busy}
          >
            Already in memory
          </Button>
          <Button
            variant="outline"
            onClick={() => onDecision("reject")}
            disabled={busy}
          >
            Not needed
          </Button>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                onClick={() => onDecision("snooze")}
                disabled={busy}
              >
                Review later
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-72">
              {REVIEW_LATER_TOOLTIP}
            </TooltipContent>
          </Tooltip>
          <Button
            variant="outline"
            onClick={() => onDecision("delete")}
            disabled={busy}
          >
            Remove
          </Button>
          {decision && (
            <Button variant="outline" onClick={onClear} disabled={busy}>
              Clear
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function MemorySweepPage() {
  const params = useParams();
  const router = useRouter();
  const classId = params.classId as string;
  const [review, setReview] = useState<MemorySweepReviewResponse | null>(null);
  const [proposal, setProposal] = useState<MemorySweepProposalResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingReason, setLoadingReason] = useState<"refresh" | "submit">(
    "refresh",
  );
  const [showAllWarnings, setShowAllWarnings] = useState(false);
  const [showReviewHelp, setShowReviewHelp] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [draftByCard, setDraftByCard] = useState<Record<string, string>>({});
  const [decisionsByCard, setDecisionsByCard] = useState<
    Record<string, MemorySweepDecision>
  >({});
  const [showDetailed, setShowDetailed] = useState(false);
  const inflightLoadRef = useRef<Promise<void> | null>(null);

  const allCandidates = useMemo(
    () =>
      proposal ? Object.values(proposal.queues).flat() : ([] as MemorySweepCandidate[]),
    [proposal],
  );
  const total = useMemo(() => countCandidates(proposal), [proposal]);
  const warningItems = useMemo(() => warningCardLinks(proposal), [proposal]);
  const warningCount = useMemo(() => uniqueWarningCount(warningItems), [warningItems]);
  const pendingCount = Object.keys(decisionsByCard).length;
  const reviewId = review?.review_id || "";
  const staleReview = Boolean(review?.is_stale || review?.status === "stale");
  const isGenerating = review?.status === "generating";
  const progressText = memorySweepProgressText(review);

  const applyReview = useCallback((next: MemorySweepReviewResponse) => {
    setReview(next);
    setProposal(proposalFromReview(next));
    const nextDecisions = decisionsByCardFromList(next.decisions ?? []);
    setDecisionsByCard(nextDecisions);
    setDraftByCard((current) => {
      const drafts = { ...current };
      for (const decision of Object.values(nextDecisions)) {
        const key = decision.card_id || decision.candidate_ids[0];
        if (key && decision.content) drafts[key] = decision.content;
      }
      return drafts;
    });
    if (typeof window === "undefined") return;
    if (next.status === "generating" && next.review_id) {
      markPendingMemorySweep(window.sessionStorage, {
        classId,
        reviewId: next.review_id,
      });
    }
  }, [classId]);

  const load = useCallback(async (
    reason: "refresh" | "submit" = "refresh",
    options?: { refresh?: boolean; keepStale?: boolean },
  ) => {
    setLoading(true);
    setLoadingReason(reason);
    setShowAllWarnings(false);
    setError(null);
    setNotice(null);
    if (options?.refresh && typeof window !== "undefined") {
      clearPendingMemorySweep(window.sessionStorage, classId);
    }
    try {
      const opened = await client.openMemorySweepReview(classId, options);
      applyReview(opened);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load Memory Sweep");
    } finally {
      setLoading(false);
    }
  }, [applyReview, classId]);

  useEffect(() => {
    // StrictMode runs this effect twice in dev; share the in-flight load so
    // each page open triggers the (LLM-backed) propose calls exactly once.
    if (!inflightLoadRef.current) {
      inflightLoadRef.current = load().finally(() => {
        inflightLoadRef.current = null;
      });
    }
  }, [load]);

  useEffect(() => {
    if (!isGenerating) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const next = await client.getMemorySweepReview(classId);
        if (!cancelled) applyReview(next);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Could not refresh Memory Sweep");
        }
      }
    };
    const interval = window.setInterval(() => void poll(), 3000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [applyReview, classId, isGenerating]);

  const persistDecisions = useCallback(
    (next: Record<string, MemorySweepDecision>) => {
      if (!reviewId) return;
      void client.patchMemorySweepReview(classId, reviewId, Object.values(next)).catch(
        (e) => {
          setError(e instanceof Error ? e.message : "Could not save review choices");
        },
      );
    },
    [classId, reviewId],
  );

  const setDecision = useCallback(
    (candidate: MemorySweepCandidate, action: MemorySweepDecision["action"]) => {
      const key = cardKey(candidate);
      const draft = draftByCard[key] ?? candidate.content;
      setDecisionsByCard((current) => {
        const next = {
          ...current,
          [key]: buildDecision(candidate, action, draft),
        };
        persistDecisions(next);
        return next;
      });
    },
    [draftByCard, persistDecisions],
  );

  const setMany = useCallback(
    (candidates: MemorySweepCandidate[], action: MemorySweepDecision["action"]) => {
      setDecisionsByCard((current) => {
        const next = { ...current };
        for (const candidate of candidates) {
          if (action === "apply" && !canApply(candidate)) continue;
          const key = cardKey(candidate);
          next[key] = buildDecision(
            candidate,
            action,
            draftByCard[key] ?? candidate.content,
          );
        }
        persistDecisions(next);
        return next;
      });
    },
    [draftByCard, persistDecisions],
  );

  const clearDecision = useCallback((candidate: MemorySweepCandidate) => {
    const key = cardKey(candidate);
    setDecisionsByCard((current) => {
      const next = { ...current };
      delete next[key];
      persistDecisions(next);
      return next;
    });
  }, [persistDecisions]);

  const updateDraft = useCallback(
    (candidate: MemorySweepCandidate, value: string) => {
      const key = cardKey(candidate);
      setDraftByCard((current) => ({ ...current, [key]: value }));
      setDecisionsByCard((current) => {
        const selected = current[key];
        if (!selected || selected.action !== "apply") return current;
        const next = { ...current, [key]: { ...selected, content: value } };
        persistDecisions(next);
        return next;
      });
    },
    [persistDecisions],
  );

  const renderCandidateCard = useCallback(
    (candidate: MemorySweepCandidate) => {
      const key = cardKey(candidate);
      return (
        <CandidateCard
          candidate={candidate}
          draft={draftByCard[key] ?? candidate.content}
          decision={decisionsByCard[key]}
          busy={busy}
          onDraftChange={(value) => updateDraft(candidate, value)}
          onDecision={(action) => setDecision(candidate, action)}
          onClear={() => clearDecision(candidate)}
        />
      );
    },
    [busy, clearDecision, decisionsByCard, draftByCard, setDecision, updateDraft],
  );

  const submit = useCallback(async () => {
    const decisions = Object.values(decisionsByCard);
    if (!reviewId) {
      setError("No saved Memory Sweep review is open.");
      return;
    }
    if (!decisions.length) {
      setError("No Memory Sweep decisions selected.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await client.patchMemorySweepReview(classId, reviewId, decisions);
      const result = await client.applyMemorySweepReview(classId, reviewId);
      const appliedText = result.applied_wiki_paths.length
        ? ` Applied to ${[...new Set(result.applied_wiki_paths)].join(", ")}.`
        : "";
      const skippedText = result.skipped.length
        ? ` Skipped: ${result.skipped.join("; ")}.`
        : "";
      setNotice(
        `Updated ${result.updated_candidate_ids.length} ledger row(s).${appliedText}${skippedText}`,
      );
      await load("submit");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit sweep decisions");
    } finally {
      setBusy(false);
    }
  }, [classId, decisionsByCard, load, reviewId, router]);

  const discard = useCallback(async () => {
    if (!reviewId) return;
    setBusy(true);
    setError(null);
    try {
      await client.discardMemorySweepReview(classId, reviewId);
      if (typeof window !== "undefined") {
        clearPendingMemorySweep(window.sessionStorage, classId);
      }
      setReview(null);
      setProposal(null);
      setDraftByCard({});
      setDecisionsByCard({});
      setNotice("Memory Sweep draft discarded.");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not discard review");
    } finally {
      setBusy(false);
    }
  }, [classId, reviewId, router]);

  return (
    <div>
      <PageHeader
        title="Memory Sweep"
        description="Review accumulated memory candidates before they become durable memory."
      />

      <div className="mb-6 flex flex-wrap gap-3">
        <Button
          onClick={() => void load("refresh", { refresh: true })}
          disabled={loading || busy || isGenerating}
        >
          {loading && review ? "Refreshing..." : reviewId ? "Refresh sweep" : "Start new sweep"}
        </Button>
        {reviewId && (
          <Button variant="outline" onClick={() => void discard()} disabled={busy}>
            Discard draft
          </Button>
        )}
        <Button variant="outline" asChild>
          <Link href={`/classes/${classId}`}>Back to class</Link>
        </Button>
      </div>

      {showReviewHelp && (
        <Alert className="mb-4 border-amber-200 bg-amber-50 text-amber-950">
          <AlertDescription>
            <div className="flex gap-3">
              <div className="flex-1 space-y-1">
                <div className="text-sm font-semibold">How to review</div>
                <p className="text-sm">
                  Each line is one suggestion: <span className="font-medium">+</span>{" "}
                  adds it to memory, <span className="font-medium">×</span> dismisses
                  it, and the clock postpones it until more evidence arrives.
                  Anything explicitly requested in chat is pinned at the top.
                  Open <span className="font-medium">details</span> on a row to edit
                  wording or see evidence; switch to{" "}
                  <span className="font-medium">Detailed</span> for the full card
                  layout.
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Dismiss review help"
                className="shrink-0 text-base leading-none text-amber-900 hover:bg-amber-100/80 hover:text-amber-950"
                onClick={() => setShowReviewHelp(false)}
              >
                ×
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert className="mb-4 border-destructive/40">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert className="mb-4 border-border bg-muted">
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}
      {staleReview && (
        <Alert className="mb-4 border-amber-200 bg-amber-50 text-amber-950">
          <AlertDescription>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm">
                This Memory Sweep draft was generated from older memory state.
              </p>
              {review?.stale_reasons?.length ? (
                <ul className="w-full list-disc space-y-1 pl-5 text-sm">
                  {review.stale_reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void load("refresh", { refresh: true })}
                  disabled={loading || busy}
                >
                  Refresh sweep
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void load("refresh", { keepStale: true })}
                  disabled={loading || busy}
                >
                  Keep reviewing
                </Button>
                {reviewId && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void discard()}
                    disabled={loading || busy}
                  >
                    Discard
                  </Button>
                )}
              </div>
            </div>
          </AlertDescription>
        </Alert>
      )}
      {isGenerating && (
        <Alert className="mb-4 border-border bg-muted">
          <AlertDescription className="flex items-center gap-2 text-sm">
            <Loader2Icon className="size-4 shrink-0 animate-spin" />
            <span>{progressText}</span>
          </AlertDescription>
        </Alert>
      )}
      {warningItems.length > 0 && (
        <Alert className="mb-4 border-border bg-muted">
          <AlertDescription>
            <div className="space-y-2">
              <p>
                {warningCount} Memory Sweep warning
                {warningCount === 1 ? "" : "s"} affect
                {" "}
                {warningItems.length} card{warningItems.length === 1 ? "" : "s"}.
              </p>
              <div className="flex flex-wrap gap-2">
                {(showAllWarnings ? warningItems : warningItems.slice(0, 2)).map(({ warning, card }) => (
                  <a
                    key={`${cardKey(card)}:${warning}`}
                    href={`#${cardDomId(card)}`}
                    className="rounded border bg-background px-2 py-1 text-xs text-foreground hover:bg-muted"
                  >
                    {card.target} / {card.section}
                  </a>
                ))}
                {warningItems.length > 2 && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-auto px-2 py-1 text-xs"
                    onClick={() => setShowAllWarnings((current) => !current)}
                  >
                    {showAllWarnings
                      ? "Show fewer"
                      : `Show ${warningItems.length - 2} more`}
                  </Button>
                )}
              </div>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {loading && !review && (
        <p className="text-sm text-muted-foreground">
          {loadingReason === "submit"
            ? "Updating saved Memory Sweep review..."
            : memorySweepLoadingSavedText()}
        </p>
      )}

      {!loading && !isGenerating && proposal && total === 0 && (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            All caught up. There are no open memory suggestions to review.
          </CardContent>
        </Card>
      )}

      {!loading && !isGenerating && allCandidates.length > 0 && (
        <div className="mb-4">
          <MemorySweepBulkToolbar
            candidates={allCandidates}
            busy={busy}
            viewMode={showDetailed ? "detailed" : "simple"}
            onViewModeChange={(mode) => setShowDetailed(mode === "detailed")}
            onBulk={setMany}
          />
        </div>
      )}

      {!loading && !isGenerating && !showDetailed && allCandidates.length > 0 && (
        <MemorySweepBrief
          candidates={allCandidates}
          decisions={decisionsByCard}
          busy={busy}
          onDecision={setDecision}
          onClear={clearDecision}
          onSubmit={() => void submit()}
          renderDetail={renderCandidateCard}
        />
      )}

      {!loading && !isGenerating && showDetailed && allCandidates.length > 0 && (
        <div className="space-y-6">
          {proposal &&
            Object.entries(proposal.queues).map(([queue, candidates]) => (
              <section key={queue} className="space-y-3">
                <h2 className="text-sm font-semibold uppercase tracking-normal text-muted-foreground">
                  {queue}
                </h2>
                <div className="grid gap-3">
                  {candidates.map((candidate) => (
                    <div key={cardKey(candidate)}>
                      {renderCandidateCard(candidate)}
                    </div>
                  ))}
                </div>
              </section>
            ))}
          <div className="sticky bottom-0 flex items-center justify-between gap-3 rounded-t-md border-t border-border bg-background/95 px-3 py-2 backdrop-blur">
            <span className="text-sm text-muted-foreground">
              {pendingCount} decision(s) selected
            </span>
            <Button
              onClick={() => void submit()}
              disabled={busy || pendingCount === 0}
            >
              {busy ? "Submitting..." : `Submit ${pendingCount} decision(s)`}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
