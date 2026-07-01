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

function canApply(candidate: MemorySweepCandidate): boolean {
  return Boolean(candidate.can_apply);
}

function cardKey(candidate: MemorySweepCandidate): string {
  return candidate.card_id || candidate.candidate_id;
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [draftByCard, setDraftByCard] = useState<Record<string, string>>({});
  const [decisionsByCard, setDecisionsByCard] = useState<
    Record<string, MemorySweepDecision>
  >({});

  const total = useMemo(() => countCandidates(proposal), [proposal]);
  const pendingCount = Object.keys(decisionsByCard).length;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await client.memorySweepPropose(classId);
      setProposal(next);
      setDraftByCard({});
      setDecisionsByCard({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load Memory Sweep");
    } finally {
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
      {proposal?.warnings?.map((warning) => (
        <Alert key={warning} className="mb-4 border-border bg-muted">
          <AlertDescription>{warning}</AlertDescription>
        </Alert>
      ))}

      {loading && <p className="text-sm text-muted-foreground">Loading candidates...</p>}

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
                    <Card key={key}>
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
