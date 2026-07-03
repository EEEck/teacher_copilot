"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  client,
  type MemorySweepCandidate,
  type MemorySweepDecision,
  type MemorySweepProposalResponse,
} from "@/lib/api";

const MEMORY_SWEEP_QUEUES = [
  "Class Evolution",
  "Subject Concepts",
  "Teacher/Copilot Preferences",
  "Wiki Review",
  "Memory Sweep",
];

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

function mergeProposal(
  current: MemorySweepProposalResponse | null,
  next: MemorySweepProposalResponse,
): MemorySweepProposalResponse {
  const queues = { ...(current?.queues ?? {}) };
  for (const [queue, candidates] of Object.entries(next.queues)) {
    queues[queue] = candidates;
  }
  return {
    class_id: next.class_id || current?.class_id || "",
    subject: next.subject || current?.subject || "",
    queues,
    warnings: [...(current?.warnings ?? []), ...(next.warnings ?? [])],
  };
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

export default function MemorySweepPage() {
  const params = useParams();
  const router = useRouter();
  const classId = params.classId as string;
  const [proposal, setProposal] = useState<MemorySweepProposalResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingQueue, setLoadingQueue] = useState<string | null>(null);
  const [loadedQueueCount, setLoadedQueueCount] = useState(0);
  const [showAllWarnings, setShowAllWarnings] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [draftByCard, setDraftByCard] = useState<Record<string, string>>({});
  const [decisionsByCard, setDecisionsByCard] = useState<
    Record<string, MemorySweepDecision>
  >({});

  const total = useMemo(() => countCandidates(proposal), [proposal]);
  const warningItems = useMemo(() => warningCardLinks(proposal), [proposal]);
  const warningCount = useMemo(() => uniqueWarningCount(warningItems), [warningItems]);
  const pendingCount = Object.keys(decisionsByCard).length;

  const load = useCallback(async () => {
    setLoading(true);
    setLoadingQueue(null);
    setLoadedQueueCount(0);
    setShowAllWarnings(false);
    setError(null);
    setNotice(null);
    setProposal(null);
    setDraftByCard({});
    setDecisionsByCard({});
    try {
      let merged: MemorySweepProposalResponse | null = null;
      for (const [index, queue] of MEMORY_SWEEP_QUEUES.entries()) {
        setLoadingQueue(queue);
        const next = await client.memorySweepPropose(classId, { queue });
        merged = mergeProposal(merged, next);
        setProposal(merged);
        setLoadedQueueCount(index + 1);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load Memory Sweep");
    } finally {
      setLoadingQueue(null);
      setLoading(false);
    }
  }, [classId]);

  useEffect(() => {
    void load();
  }, [load]);

  const setDecision = useCallback(
    (candidate: MemorySweepCandidate, action: MemorySweepDecision["action"]) => {
      const key = cardKey(candidate);
      const draft = draftByCard[key] ?? candidate.content;
      setDecisionsByCard((current) => ({
        ...current,
        [key]: buildDecision(candidate, action, draft),
      }));
    },
    [draftByCard],
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
        return next;
      });
    },
    [draftByCard],
  );

  const clearDecision = useCallback((candidate: MemorySweepCandidate) => {
    const key = cardKey(candidate);
    setDecisionsByCard((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }, []);

  const submit = useCallback(async () => {
    const decisions = Object.values(decisionsByCard);
    if (!decisions.length) {
      setError("No Memory Sweep decisions selected.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await client.memorySweepApply(classId, decisions);
      const appliedText = result.applied_wiki_paths.length
        ? ` Applied to ${[...new Set(result.applied_wiki_paths)].join(", ")}.`
        : "";
      const skippedText = result.skipped.length
        ? ` Skipped: ${result.skipped.join("; ")}.`
        : "";
      setNotice(
        `Updated ${result.updated_candidate_ids.length} ledger row(s).${appliedText}${skippedText}`,
      );
      await load();
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit sweep decisions");
    } finally {
      setBusy(false);
    }
  }, [classId, decisionsByCard, load, router]);

  return (
    <div>
      <PageHeader
        title="Memory Sweep"
        description="Review accumulated memory candidates before they become durable memory."
      />

      <div className="mb-6 flex flex-wrap gap-3">
        <Button onClick={() => void load()} disabled={loading || busy}>
          {loading ? "Refreshing..." : "Refresh"}
        </Button>
        <Button onClick={() => void submit()} disabled={busy || pendingCount === 0}>
          {busy ? "Submitting..." : `Submit ${pendingCount} decision(s)`}
        </Button>
        <Button variant="outline" asChild>
          <Link href={`/classes/${classId}`}>Back to class</Link>
        </Button>
      </div>

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

      {loading && (
        <p className="text-sm text-muted-foreground">
          {loadingQueue
            ? `Loaded ${loadedQueueCount} of ${MEMORY_SWEEP_QUEUES.length} queues · Loading ${loadingQueue}...`
            : "Loading Memory Sweep queues..."}
        </p>
      )}

      {!loading && proposal && total === 0 && (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            No open memory candidates.
          </CardContent>
        </Card>
      )}

      <div className="space-y-6">
        {proposal &&
          Object.entries(proposal.queues).map(([queue, candidates]) => (
            <section key={queue} className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-sm font-semibold uppercase tracking-normal text-muted-foreground">
                  {queue}
                </h2>
                <div className="flex flex-wrap gap-2">
                  {candidates.some(canApply) && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setMany(candidates, "apply")}
                      disabled={busy}
                    >
                      Select apply supported
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setMany(candidates, "reject")}
                    disabled={busy}
                  >
                    Select reject queue
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setMany(candidates, "snooze")}
                    disabled={busy}
                  >
                    Select snooze queue
                  </Button>
                </div>
              </div>
              <div className="grid gap-3">
                {candidates.map((candidate) => {
                  const key = cardKey(candidate);
                  const applicable = canApply(candidate);
                  const draft = draftByCard[key] ?? candidate.content;
                  const decision = decisionsByCard[key];
                  return (
                    <Card key={key} id={cardDomId(candidate)} className="scroll-mt-6">
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
                          {candidate.signal_count > 1 && (
                            <span>{candidate.signal_count} signals</span>
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
                                <div className="mb-1 font-medium text-foreground">
                                  Replace
                                </div>
                                <p className="whitespace-pre-wrap text-muted-foreground">
                                  {candidate.replaces_content || "Missing replacement source"}
                                </p>
                                <div className="mb-1 mt-3 font-medium text-foreground">
                                  With
                                </div>
                              </div>
                            )}
                            <Textarea
                              value={draft}
                              onChange={(e) => {
                                const nextDraft = e.target.value;
                                setDraftByCard((current) => ({
                                  ...current,
                                  [key]: nextDraft,
                                }));
                                setDecisionsByCard((current) => {
                                  const selected = current[key];
                                  if (!selected || selected.action !== "apply") return current;
                                  return {
                                    ...current,
                                    [key]: { ...selected, content: nextDraft },
                                  };
                                });
                              }}
                              disabled={busy}
                              className="min-h-24 text-sm"
                            />
                          </div>
                        ) : (
                          <p className="text-sm">{candidate.content}</p>
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
                            <Button
                              onClick={() => setDecision(candidate, "apply")}
                              disabled={busy}
                            >
                              {(candidate.operation ?? "add") === "adjust"
                                ? "Apply adjustment"
                                : "Add memory"}
                            </Button>
                          )}
                          <Button
                            variant="outline"
                            onClick={() => setDecision(candidate, "already_covered")}
                            disabled={busy}
                          >
                            Already covered
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => setDecision(candidate, "reject")}
                            disabled={busy}
                          >
                            Reject
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => setDecision(candidate, "snooze")}
                            disabled={busy}
                          >
                            Snooze
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => setDecision(candidate, "delete")}
                            disabled={busy}
                          >
                            Delete
                          </Button>
                          {decision && (
                            <Button
                              variant="outline"
                              onClick={() => clearDecision(candidate)}
                              disabled={busy}
                            >
                              Clear
                            </Button>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </section>
          ))}
      </div>
    </div>
  );
}
