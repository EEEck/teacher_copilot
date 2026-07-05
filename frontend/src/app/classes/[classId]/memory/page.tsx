"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useArtifactSession } from "@/components/assistant-ui/artifact-session-runtime";
import { IngestThread } from "@/components/assistant-ui/ingest-thread";
import {
  ArtifactSessionPage,
  type ArtifactSessionBodyProps,
} from "@/components/klassenpilot/artifact-session-page";
import { ArtifactSessionWorkspace } from "@/components/klassenpilot/artifact-session-workspace";
import { DiaryDraftPanel } from "@/components/klassenpilot/diary-draft-panel";
import { ProposedMemoryUpdates } from "@/components/klassenpilot/proposed-memory-updates";
import {
  MarkdownLineDiff,
  ReviewBrief,
  useFileChangeReview,
  WikiProposalEditor,
} from "@/components/klassenpilot/review";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  client,
  uniqueWikiProposals,
  type IngestStartHint,
  type MemoryCandidate,
  type MemoryProposalResponse,
  type WikiUpdateProposal,
} from "@/lib/api";
import { isMemoryReviewSaveDisabled } from "@/lib/memory-save-guards";
import {
  clearPendingMemoryReview,
  loadPendingMemoryReview,
  savePendingMemoryReview,
} from "@/lib/pending-memory-review";

type CommitResult = {
  lesson_date: string;
  title: string;
  log_entry_id: string;
  applied_wiki_paths: string[];
};

const COMPACT_PAGE_LABELS: Record<string, string> = {
  class_state: "Class state",
  taught_so_far: "Taught so far",
  planning_brief: "Planning brief",
  teaching_patterns: "Teaching patterns",
  copilot_profile: "Class copilot profile",
  session_summaries: "Session summaries",
};

function ReadyToSaveButton({ onReady, loading }: { onReady: () => void; loading: boolean }) {
  const { isUpdating, readyToSave } = useArtifactSession();

  return (
    <div className="flex flex-col gap-1">
      <Button className="w-fit" onClick={onReady} disabled={loading || isUpdating}>
        {loading ? "Compiling wiki updates…" : "Ready to save memory"}
      </Button>
      {readyToSave && !loading && (
        <p className="text-xs text-primary">
          All sections filled — compile and review wiki file changes before saving.
        </p>
      )}
    </div>
  );
}

function textFromRecord(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function boolFromRecord(value: unknown): boolean {
  return typeof value === "boolean" ? value : false;
}

function normalizeMemoryCandidates(value: unknown): MemoryCandidate[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is MemoryCandidate =>
      !!item &&
      typeof item === "object" &&
      typeof (item as MemoryCandidate).target === "string" &&
      typeof (item as MemoryCandidate).candidate_update === "string",
  );
}

function dedupeMemoryCandidates(candidates: MemoryCandidate[]): MemoryCandidate[] {
  const seen = new Set<string>();
  const out: MemoryCandidate[] = [];
  for (const c of candidates) {
    const key = `${c.target}::${c.section ?? ""}::${c.candidate_update.trim().toLowerCase()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(c);
  }
  return out;
}

function CompactMemoryProposalCard({
  proposal,
  applying,
  onApply,
  onContinue,
}: {
  proposal: MemoryProposalResponse;
  applying: boolean;
  onApply: (pages: Record<string, string>) => void;
  onContinue: () => void;
}) {
  const pageKeys = useMemo(() => Object.keys(proposal.pages ?? {}), [proposal.pages]);
  const [approved, setApproved] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(pageKeys.map((key) => [key, true])),
  );
  const approvedPages = Object.fromEntries(
    pageKeys
      .filter((key) => approved[key])
      .map((key) => [key, proposal.pages[key]]),
  );
  const approvedCount = Object.keys(approvedPages).length;

  if (!pageKeys.length && !proposal.warnings.length) return null;

  return (
    <Card variant="highlight" size="sm">
      <CardHeader>
        <CardTitle>Refresh class memory</CardTitle>
        <p className="text-sm text-muted-foreground">
          Review the compact class-memory pages generated from the saved lesson.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {proposal.warnings.length > 0 && (
          <ul className="space-y-1 text-xs text-destructive">
            {proposal.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        )}
        <ul className="flex flex-col gap-3">
          {pageKeys.map((key) => {
            const preview = proposal.pages[key]
              .split("\n")
              .filter((line) => line.trim() && !line.startsWith("#"))
              .slice(0, 2)
              .join(" ");
            return (
              <li key={key} className="flex items-start gap-2">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={!!approved[key]}
                  disabled={applying}
                  onChange={(e) =>
                    setApproved((prev) => ({ ...prev, [key]: e.target.checked }))
                  }
                />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">
                    {COMPACT_PAGE_LABELS[key] ?? key}
                  </div>
                  {preview && (
                    <p className="line-clamp-2 text-xs text-muted-foreground">
                      {preview}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </CardContent>
      <div className="flex flex-wrap gap-3 px-6 pb-6">
        {pageKeys.length > 0 && (
          <Button
            onClick={() => onApply(approvedPages)}
            disabled={applying || approvedCount === 0}
          >
            {applying ? "Applying..." : `Apply ${approvedCount} page(s)`}
          </Button>
        )}
        <Button variant="outline" onClick={onContinue} disabled={applying}>
          Skip for now
        </Button>
      </div>
    </Card>
  );
}

function MemoryTargetStatus() {
  const { memoryState, lastChangeSummary } = useArtifactSession();
  if (!memoryState) return null;
  const target = memoryState.target;
  const targetRecord = target && typeof target === "object" ? (target as Record<string, unknown>) : {};
  const phase = textFromRecord(memoryState.phase);
  const intent = textFromRecord(memoryState.intent);
  const date = textFromRecord(targetRecord.lesson_date);
  const title = textFromRecord(targetRecord.lesson_title);
  const confirmed = boolFromRecord(targetRecord.target_confirmed);

  return (
    <Card className="border-border bg-muted/40">
      <CardContent className="flex flex-wrap items-center gap-x-4 gap-y-1 p-3 text-xs">
        <span className="font-medium text-foreground">
          {date ? `Target: ${date}${title ? ` · ${title}` : ""}` : "Target: not selected"}
        </span>
        {intent && <span className="text-muted-foreground">Intent: {intent}</span>}
        {phase && <span className="text-muted-foreground">Phase: {phase}</span>}
        <span className={confirmed ? "text-primary" : "text-muted-foreground"}>
          {confirmed ? "Confirmed" : "Needs confirmation"}
        </span>
        {lastChangeSummary && (
          <span className="basis-full text-muted-foreground">{lastChangeSummary}</span>
        )}
      </CardContent>
    </Card>
  );
}

function MemoryWorkspace({
  classId,
  reviewStorageKey,
  onError,
}: {
  classId: string;
  reviewStorageKey: string;
  onError: (message: string | null) => void;
}) {
  const router = useRouter();
  const {
    artifactMarkdown: diaryMarkdown,
    isUpdating,
    runWithSessionRecovery,
    setArtifactMarkdown,
  } = useArtifactSession();
  const [proposals, setProposals] = useState<WikiUpdateProposal[]>([]);
  const [loading, setLoading] = useState(false);
  const [inReview, setInReview] = useState(false);
  const [editingWiki, setEditingWiki] = useState(false);
  const [commitResult, setCommitResult] = useState<CommitResult | null>(null);
  const [memoryCandidates, setMemoryCandidates] = useState<MemoryCandidate[]>([]);
  const [applyingMemory, setApplyingMemory] = useState(false);
  const [classMemoryProposal, setClassMemoryProposal] =
    useState<MemoryProposalResponse | null>(null);
  const [applyingClassMemory, setApplyingClassMemory] = useState(false);
  const restoredReviewRef = useRef(false);

  const {
    items: reviewItems,
    selected: selectedChange,
    selectedPath,
    setSelectedPath,
    contentByPath,
    updateContent,
    getCommitPayload,
    setApproved,
    approveAll,
    initFromProposals,
    clear: clearReview,
    hasLessonResultsApproved,
    approvedByPath,
  } = useFileChangeReview(proposals);

  useEffect(() => {
    if (restoredReviewRef.current) return;
    restoredReviewRef.current = true;
    if (typeof window === "undefined") return;

    const pending = loadPendingMemoryReview(
      window.sessionStorage,
      classId,
      reviewStorageKey,
    );
    if (!pending) return;

    setArtifactMarkdown(pending.diaryMarkdown, "agent");
    setMemoryCandidates(pending.memoryCandidates);
    setProposals(pending.proposals);
    initFromProposals(pending.proposals);
    for (const [path, content] of Object.entries(pending.contentByPath)) {
      updateContent(path, content);
    }
    for (const [path, approved] of Object.entries(pending.approvedByPath)) {
      setApproved(path, approved);
    }
    if (pending.selectedPath) setSelectedPath(pending.selectedPath);
    setEditingWiki(pending.editingWiki);
    setInReview(true);
  }, [
    classId,
    initFromProposals,
    reviewStorageKey,
    setApproved,
    setArtifactMarkdown,
    setSelectedPath,
    updateContent,
  ]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!inReview || proposals.length === 0) return;

    savePendingMemoryReview(window.sessionStorage, {
      classId,
      routeKey: reviewStorageKey,
      diaryMarkdown,
      proposals,
      memoryCandidates,
      approvedByPath,
      contentByPath,
      selectedPath,
      editingWiki,
    });
  }, [
    approvedByPath,
    classId,
    contentByPath,
    diaryMarkdown,
    editingWiki,
    inReview,
    memoryCandidates,
    proposals,
    reviewStorageKey,
    selectedPath,
  ]);

  useEffect(() => {
    if (!inReview || proposals.length === 0) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [inReview, proposals.length]);

  const selectFile = useCallback(
    (path: string) => {
      setSelectedPath(path);
      setEditingWiki(true);
    },
    [setSelectedPath],
  );

  const viewerAllHref = commitResult
    ? `/classes/${classId}/wiki/view?paths=${encodeURIComponent(commitResult.applied_wiki_paths.join(","))}`
    : "";
  const reviewActionsDisabled = loading || isUpdating;
  const reviewSaveDisabled = isMemoryReviewSaveDisabled({
    saving: loading,
    isUpdating,
    hasLessonResultsApproved,
  });

  const handleReadyToSave = useCallback(async () => {
    if (isUpdating) {
      onError("Wait for the current chat turn to finish before preparing wiki updates.");
      return;
    }
    setLoading(true);
    onError(null);
    setCommitResult(null);
    setClassMemoryProposal(null);
    try {
      await runWithSessionRecovery((sessionId) =>
        client.ingestUpdateDraft(classId, sessionId, diaryMarkdown),
      );
      const d = await runWithSessionRecovery((sessionId) =>
        client.ingestPropose(classId, sessionId),
      );
      const unique = uniqueWikiProposals(d.wiki_proposals);
      setMemoryCandidates(
        dedupeMemoryCandidates(
          d.memory_candidates?.length
            ? d.memory_candidates
            : normalizeMemoryCandidates(d.memory_state?.memory_candidates),
        ),
      );
      setProposals(unique);
      initFromProposals(unique);
      setInReview(true);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not prepare save");
    } finally {
      setLoading(false);
    }
  }, [classId, diaryMarkdown, isUpdating, onError, runWithSessionRecovery, initFromProposals]);

  const commit = useCallback(async () => {
    if (isUpdating) {
      onError("Wait for the current chat turn to finish before saving memory.");
      return;
    }
    setLoading(true);
    onError(null);
    try {
      const result = await runWithSessionRecovery((sessionId) =>
        client.ingestCommit(classId, sessionId, diaryMarkdown, getCommitPayload()),
      );
      setCommitResult({
        lesson_date: result.lesson_date,
        title: result.title,
        log_entry_id: result.log_entry_id,
        applied_wiki_paths: result.applied_wiki_paths,
      });
      const proposal = result.class_memory_proposal;
      setClassMemoryProposal(
        proposal && (Object.keys(proposal.pages ?? {}).length > 0 || proposal.warnings.length > 0)
          ? proposal
          : null,
      );
      setInReview(false);
      setProposals([]);
      clearReview();
      if (typeof window !== "undefined") {
        clearPendingMemoryReview(window.sessionStorage, classId, reviewStorageKey);
      }
      router.refresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Commit failed");
    } finally {
      setLoading(false);
    }
  }, [classId, diaryMarkdown, getCommitPayload, clearReview, isUpdating, onError, reviewStorageKey, router, runWithSessionRecovery]);

  const applyClassMemory = useCallback(
    async (pages: Record<string, string>) => {
      setApplyingClassMemory(true);
      onError(null);
      try {
        if (!classMemoryProposal) return;
        await client.memoryCompactApply(
          classId,
          pages,
          classMemoryProposal.source_paths ?? [],
        );
        setClassMemoryProposal(null);
        router.refresh();
      } catch (e) {
        onError(e instanceof Error ? e.message : "Could not refresh class memory");
      } finally {
        setApplyingClassMemory(false);
      }
    },
    [classId, classMemoryProposal, onError, router],
  );

  const applyMemory = useCallback(
    async (approved: MemoryCandidate[]) => {
      setApplyingMemory(true);
      onError(null);
      try {
        await client.memoryApply(
          classId,
          approved.map((c) => ({
            target: c.target,
            section: c.section,
            content: c.candidate_update,
          })),
        );
        setMemoryCandidates([]);
        router.refresh();
      } catch (e) {
        onError(e instanceof Error ? e.message : "Could not apply memory updates");
      } finally {
        setApplyingMemory(false);
      }
    },
    [classId, onError, router],
  );

  const keepAll = useCallback(() => {
    approveAll();
    void commit();
  }, [approveAll, commit]);

  const undoAll = useCallback(() => {
    setInReview(false);
    setEditingWiki(false);
    setProposals([]);
    setMemoryCandidates([]);
    setClassMemoryProposal(null);
    clearReview();
    if (typeof window !== "undefined") {
      clearPendingMemoryReview(window.sessionStorage, classId, reviewStorageKey);
    }
    onError(null);
  }, [classId, onError, clearReview, reviewStorageKey]);

  const draftPanel =
    inReview && editingWiki && selectedPath && selectedPath in contentByPath ? (
      <WikiProposalEditor
        wikiPath={selectedPath}
        markdown={contentByPath[selectedPath]}
        onChange={(value) => updateContent(selectedPath, value)}
        onBackToDiary={() => setEditingWiki(false)}
      />
    ) : (
      <DiaryDraftPanel />
    );

  return (
    <div className="space-y-8">
      <MemoryTargetStatus />
      <ArtifactSessionWorkspace
        thread={<IngestThread />}
        draftPanel={draftPanel}
        footer={
          !inReview ? <ReadyToSaveButton onReady={handleReadyToSave} loading={loading} /> : null
        }
        reviewDiff={
          inReview && editingWiki && selectedChange ? (
            <MarkdownLineDiff
              path={selectedChange.path}
              before={selectedChange.before}
              after={selectedChange.after}
              className="h-full min-h-[12rem]"
            />
          ) : null
        }
        reviewFileList={
          inReview && reviewItems.length > 0 ? (
            <ReviewBrief
              items={reviewItems}
              selectedPath={selectedPath ?? reviewItems[0]?.path ?? null}
              onSelectPath={selectFile}
              onSetApproved={setApproved}
              onUndoAll={undoAll}
              onKeepAll={keepAll}
              onSave={commit}
              saving={reviewActionsDisabled}
              actionsDisabled={reviewActionsDisabled}
              saveDisabled={reviewSaveDisabled}
            />
          ) : null
        }
      />

      {inReview && !hasLessonResultsApproved && (
        <p className="text-xs text-destructive">
          Keep the lesson results change selected to save this lesson to memory.
        </p>
      )}

      {commitResult && (
        <Card variant="highlight">
          <CardHeader>
            <CardTitle className="text-base">Memory saved</CardTitle>
            <p className="text-sm text-muted-foreground">
              {commitResult.title} ({commitResult.lesson_date}) — log entry{" "}
              <span className="font-mono text-xs">{commitResult.log_entry_id}</span>
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-foreground">
              {commitResult.applied_wiki_paths.length} file
              {commitResult.applied_wiki_paths.length === 1 ? "" : "s"} updated.
            </p>
            <ul className="space-y-1 text-sm">
              {commitResult.applied_wiki_paths.map((path) => (
                <li key={path}>
                  <Link
                    href={`/classes/${classId}/wiki/view?path=${encodeURIComponent(path)}`}
                    className="font-mono text-xs text-primary hover:underline"
                  >
                    {path}
                  </Link>
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-3 pt-1">
              <Button asChild>
                <Link href={viewerAllHref}>View all changes</Link>
              </Button>
              <Button variant="outline" asChild>
                <Link
                  href={
                    commitResult.lesson_date
                      ? `/classes/${classId}?highlight=${encodeURIComponent(commitResult.lesson_date)}`
                      : `/classes/${classId}`
                  }
                >
                  Back to class home
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {commitResult && memoryCandidates.length > 0 && (
        <ProposedMemoryUpdates
          candidates={memoryCandidates}
          onApply={applyMemory}
          applying={applyingMemory}
          onContinue={() => setMemoryCandidates([])}
          continueLabel="Skip for now"
        />
      )}

      {commitResult && classMemoryProposal && (
        <CompactMemoryProposalCard
          key={`${commitResult.log_entry_id}-class-memory`}
          proposal={classMemoryProposal}
          onApply={applyClassMemory}
          applying={applyingClassMemory}
          onContinue={() => setClassMemoryProposal(null)}
        />
      )}
    </div>
  );
}

function MemoryPageContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const classId = params.classId as string;
  const reviewStorageKey = useMemo(() => {
    const qs = searchParams.toString();
    return `/classes/${classId}/memory${qs ? `?${qs}` : ""}`;
  }, [classId, searchParams]);
  const startHint = useMemo<IngestStartHint | undefined>(() => {
    const lessonDate = searchParams.get("lessonDate") ?? "";
    if (!lessonDate) return undefined;
    const intent = searchParams.get("intent") ?? "";
    const targetKind = searchParams.get("targetKind") ?? "";
    return {
      lesson_date: lessonDate,
      lesson_title: searchParams.get("lessonTitle") ?? undefined,
      intent: intent === "correct_existing_results" ? intent : "update_missing_results",
      target_kind:
        targetKind === "taught_lesson" || targetKind === "new_lesson"
          ? targetKind
          : "planned_lesson",
      source: "timeline_hint",
    };
  }, [searchParams]);

  const bootstrap = useCallback(
    async (opts?: { preserveMarkdown?: string }) => {
      const session = await client.startIngestSession(classId, startHint);
      let draft = await client.ingestGetDraft(classId, session.session_id);
      if (opts?.preserveMarkdown) {
        draft = await client.ingestUpdateDraft(
          classId,
          session.session_id,
          opts.preserveMarkdown,
        );
      }
      return {
        sessionId: session.session_id,
        initialMarkdown: draft.diary_markdown,
        initialCompleteness: draft.completeness,
        initialMemoryState: draft.memory_state ?? session.memory_state ?? null,
      };
    },
    [classId, startHint],
  );

  return (
    <ArtifactSessionPage
      mode="ingest"
      classId={classId}
      title="Update memory"
      description={
        startHint?.lesson_date
          ? `Updating memory for ${startHint.lesson_date}`
          : "Chat through the lesson, edit the diary on the right, then save when ready."
      }
      bootstrap={bootstrap}
      renderBody={({ onError }: ArtifactSessionBodyProps) => (
        <MemoryWorkspace
          classId={classId}
          reviewStorageKey={reviewStorageKey}
          onError={onError}
        />
      )}
    />
  );
}

export default function MemoryPage() {
  return (
    <Suspense fallback={<p className="text-muted-foreground">Loading memory...</p>}>
      <MemoryPageContent />
    </Suspense>
  );
}
