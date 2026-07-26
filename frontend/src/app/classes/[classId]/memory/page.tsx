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
import {
  MarkdownLineDiff,
  ReviewBrief,
  useFileChangeReview,
  WikiProposalEditor,
} from "@/components/klassenpilot/review";
import { WorkflowActionNeededCard } from "@/components/klassenpilot/workflow";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  client,
  uniqueWikiProposals,
  type IngestStartHint,
  type MemoryCandidate,
  type WikiUpdateProposal,
} from "@/lib/api";
import { markClassHomeTimelineRefresh } from "@/lib/class-home-refresh";
import { memoryDiscardRedirectHref } from "@/lib/memory-discard-routing";
import {
  getReadyToSaveButtonLabel,
  type MemoryFooterOperation,
} from "@/lib/memory-footer-state";
import {
  isMemoryReCommitBlocked,
  isMemoryReviewSaveDisabled,
  shouldShowReviewBrief,
} from "@/lib/memory-save-guards";
import {
  clearPendingMemoryReview,
  loadPendingMemoryReview,
  savePendingMemoryReview,
} from "@/lib/pending-memory-review";
import {
  classifyWorkflowError,
  routeWorkflowError,
} from "@/lib/workflow-error";
import { useWorkflowDraftStore } from "@/features/workflow-drafts/workflow-draft-store";
import { useAuiState } from "@assistant-ui/react";

type CommitResult = {
  lesson_date: string;
  title: string;
  log_entry_id: string;
  applied_wiki_paths: string[];
};

/** Brief pause so the teacher sees “Memory saved” before class-home highlight. */
const POST_COMMIT_HOME_DELAY_MS = 3000;

function ReadyToSaveButton({
  onReady,
  operation,
  disabled = false,
}: {
  onReady: () => void;
  operation: MemoryFooterOperation;
  disabled?: boolean;
}) {
  const { isUpdating } = useArtifactSession();
  const hasDraftMessage = useAuiState((s) => !s.composer.isEmpty);
  const compiling = operation === "compiling";

  return (
    <Button
      type="button"
      className="w-fit"
      onClick={onReady}
      disabled={disabled || compiling || isUpdating || hasDraftMessage}
    >
      {getReadyToSaveButtonLabel(operation)}
    </Button>
  );
}

function textFromRecord(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function boolFromRecord(value: unknown): boolean {
  return typeof value === "boolean" ? value : false;
}

function MemoryTargetStatus() {
  const { memoryState, lastChangeSummary, memoryCandidates } = useArtifactSession();
  if (!memoryState) return null;
  const target = memoryState.target;
  const targetRecord = target && typeof target === "object" ? (target as Record<string, unknown>) : {};
  const phase = textFromRecord(memoryState.phase);
  const intent = textFromRecord(memoryState.intent);
  const date = textFromRecord(targetRecord.lesson_date);
  const title = textFromRecord(targetRecord.lesson_title);
  const confirmed = boolFromRecord(targetRecord.target_confirmed);
  const stagedCount = memoryCandidates.length;

  return (
    <div className="space-y-1 rounded-md border border-border bg-muted/40 px-2.5 py-1.5 text-[11px] leading-tight">
      <p className="text-muted-foreground">
        Session status — which lesson this diary is for and the last draft
        change (not a chat message).
      </p>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <span className="font-medium text-foreground">
          {date ? `Target: ${date}${title ? ` · ${title}` : ""}` : "Target: not selected"}
        </span>
        {intent && <span className="text-muted-foreground">Intent: {intent}</span>}
        {phase && <span className="text-muted-foreground">Phase: {phase}</span>}
        <span className={confirmed ? "text-primary" : "text-muted-foreground"}>
          {confirmed ? "Confirmed" : "Needs confirmation"}
        </span>
      </div>
      {lastChangeSummary && (
        <p className="text-muted-foreground">Last change: {lastChangeSummary}</p>
      )}
      {stagedCount > 0 && (
        <p className="text-muted-foreground">
          {stagedCount} staged for Memory Sweep (wiki unchanged)
        </p>
      )}
    </div>
  );
}

function MemoryWorkspace({
  classId,
  reviewStorageKey,
  discardRedirectHref,
  onError,
}: {
  classId: string;
  reviewStorageKey: string;
  discardRedirectHref?: string | null;
  onError: (message: string | null) => void;
}) {
  const router = useRouter();
  const {
    draftId,
    artifactRevision,
    artifactHash,
    artifactMarkdown: diaryMarkdown,
    isUpdating,
    readyToSave,
    runWithSessionRecovery,
    setArtifactMarkdown,
  } = useArtifactSession();
  const [proposals, setProposals] = useState<WikiUpdateProposal[]>([]);
  const [loading, setLoading] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const [inReview, setInReview] = useState(false);
  const [editingWiki, setEditingWiki] = useState(false);
  const [commitResult, setCommitResult] = useState<CommitResult | null>(null);
  const commitResultRef = useRef<HTMLDivElement>(null);
  const [memoryCandidates, setMemoryCandidates] = useState<MemoryCandidate[]>([]);
  const [reviewBaseMarkdown, setReviewBaseMarkdown] = useState<string | null>(null);
  const [reviewSnapshot, setReviewSnapshot] = useState<{
    draftId: string;
    artifactRevision: number;
    artifactHash: string;
  } | null>(null);
  const [actionNeeded, setActionNeeded] = useState<{
    message: string;
    respondInChat: boolean;
  } | null>(null);
  const restoredReviewRef = useRef(false);
  const hasDraftMessage = useAuiState((s) => !s.composer.isEmpty);

  const clearWorkflowErrors = useCallback(() => {
    onError(null);
    setActionNeeded(null);
  }, [onError]);

  const reportWorkflowError = useCallback(
    (error: unknown, fallback: string) => {
      routeWorkflowError(classifyWorkflowError(error, fallback), {
        onActionNeeded: setActionNeeded,
        onSystem: onError,
      });
    },
    [onError],
  );

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
    if (
      pending.draftId !== draftId ||
      pending.sourceArtifactRevision !== artifactRevision ||
      pending.sourceArtifactHash !== artifactHash
    ) {
      clearPendingMemoryReview(window.sessionStorage, classId, reviewStorageKey);
      return;
    }

    setArtifactMarkdown(pending.diaryMarkdown, "agent");
    setMemoryCandidates(pending.memoryCandidates);
    setProposals(pending.proposals);
    setReviewBaseMarkdown(pending.diaryMarkdown);
    setReviewSnapshot({
      draftId: pending.draftId,
      artifactRevision: pending.sourceArtifactRevision,
      artifactHash: pending.sourceArtifactHash,
    });
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
    artifactHash,
    artifactRevision,
    classId,
    draftId,
    initFromProposals,
    reviewStorageKey,
    setApproved,
    setArtifactMarkdown,
    setSelectedPath,
    updateContent,
  ]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!inReview || proposals.length === 0 || !reviewSnapshot) return;

    savePendingMemoryReview(window.sessionStorage, {
      classId,
      routeKey: reviewStorageKey,
      draftId: reviewSnapshot.draftId,
      sourceArtifactRevision: reviewSnapshot.artifactRevision,
      sourceArtifactHash: reviewSnapshot.artifactHash,
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
    reviewSnapshot,
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

  useEffect(() => {
    if (!isUpdating || (!inReview && proposals.length === 0)) return;
    setInReview(false);
    setEditingWiki(false);
    setProposals([]);
    setMemoryCandidates([]);
    setReviewBaseMarkdown(null);
    setReviewSnapshot(null);
    clearReview();
    if (typeof window !== "undefined") {
      clearPendingMemoryReview(window.sessionStorage, classId, reviewStorageKey);
    }
  }, [classId, clearReview, inReview, isUpdating, proposals.length, reviewStorageKey]);

  useEffect(() => {
    if (!inReview || proposals.length === 0 || reviewBaseMarkdown === null) return;
    if (diaryMarkdown === reviewBaseMarkdown) return;
    setInReview(false);
    setEditingWiki(false);
    setProposals([]);
    setMemoryCandidates([]);
    setReviewBaseMarkdown(null);
    setReviewSnapshot(null);
    clearReview();
    if (typeof window !== "undefined") {
      clearPendingMemoryReview(window.sessionStorage, classId, reviewStorageKey);
    }
  }, [
    classId,
    clearReview,
    diaryMarkdown,
    inReview,
    proposals.length,
    reviewBaseMarkdown,
    reviewStorageKey,
  ]);

  const selectFile = useCallback(
    (path: string) => {
      setSelectedPath(path);
      setEditingWiki(true);
    },
    [setSelectedPath],
  );

  const handleDiscardDraft = useCallback(async () => {
    if (!draftId) return;
    setDiscarding(true);
    clearWorkflowErrors();
    try {
      await client.discardWorkflowDraft(classId, draftId);
      useWorkflowDraftStore.getState().remove(draftId);
      if (typeof window !== "undefined") {
        clearPendingMemoryReview(window.sessionStorage, classId, reviewStorageKey);
        window.sessionStorage.removeItem(`kp:composer:${draftId}`);
        markClassHomeTimelineRefresh(window.sessionStorage, classId);
        if (discardRedirectHref) {
          router.replace(discardRedirectHref);
        } else {
          window.location.reload();
        }
      }
    } catch (e) {
      reportWorkflowError(e, "Could not discard draft");
      setDiscarding(false);
    }
  }, [
    classId,
    clearWorkflowErrors,
    discardRedirectHref,
    draftId,
    reportWorkflowError,
    reviewStorageKey,
    router,
  ]);

  const homeHrefAfterCommit = commitResult
    ? commitResult.lesson_date
      ? `/classes/${classId}?highlight=${encodeURIComponent(commitResult.lesson_date)}`
      : `/classes/${classId}`
    : `/classes/${classId}`;

  // Brief success flash, then auto-return to class home (timeline highlight ring).
  useEffect(() => {
    if (!commitResult) return;
    commitResultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    const timer = window.setTimeout(() => {
      router.push(homeHrefAfterCommit);
    }, POST_COMMIT_HOME_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [commitResult, homeHrefAfterCommit, router]);

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
    if (hasDraftMessage) {
      onError("Send or clear the draft message before preparing wiki updates.");
      return;
    }
    setLoading(true);
    clearWorkflowErrors();
    setCommitResult(null);
    try {
      await runWithSessionRecovery((sessionId) =>
        client.ingestUpdateDraft(classId, sessionId, diaryMarkdown),
      );
      const d = await runWithSessionRecovery((sessionId) =>
        client.ingestPropose(classId, sessionId),
      );
      const unique = uniqueWikiProposals(d.wiki_proposals);
      // Preference candidates stay in the ledger for Sweep — not a post-save UI list.
      setMemoryCandidates([]);
      setProposals(unique);
      setReviewBaseMarkdown(d.diary_markdown);
      setReviewSnapshot({
        draftId: d.draft_id,
        artifactRevision: d.artifact_revision,
        artifactHash: d.artifact_hash,
      });
      initFromProposals(unique);
      setInReview(true);
    } catch (e) {
      reportWorkflowError(e, "Could not prepare save");
    } finally {
      setLoading(false);
    }
  }, [
    classId,
    clearWorkflowErrors,
    diaryMarkdown,
    hasDraftMessage,
    isUpdating,
    onError,
    reportWorkflowError,
    runWithSessionRecovery,
    initFromProposals,
  ]);

  const commit = useCallback(async () => {
    if (isUpdating) {
      onError("Wait for the current chat turn to finish before saving memory.");
      return;
    }
    // Idempotency: this review already committed (the confirmation is showing).
    // Re-entry here would write the lesson a second time — the double-commit
    // seen in beta telemetry. A new review cycle clears commitResult first.
    if (isMemoryReCommitBlocked({ saving: loading, alreadyCommitted: !!commitResult })) {
      return;
    }
    setLoading(true);
    clearWorkflowErrors();
    try {
      const result = await runWithSessionRecovery((sessionId) =>
        client.ingestCommit(classId, sessionId, diaryMarkdown, getCommitPayload(), {
          draftId: reviewSnapshot?.draftId ?? draftId,
          expectedArtifactRevision: reviewSnapshot?.artifactRevision ?? artifactRevision,
          expectedArtifactHash: reviewSnapshot?.artifactHash ?? artifactHash,
          sourceArtifactRevision: reviewSnapshot?.artifactRevision ?? artifactRevision,
          sourceArtifactHash: reviewSnapshot?.artifactHash ?? artifactHash,
        }),
      );
      setCommitResult({
        lesson_date: result.lesson_date,
        title: result.title,
        log_entry_id: result.log_entry_id,
        applied_wiki_paths: result.applied_wiki_paths,
      });
      setMemoryCandidates([]);
      setInReview(false);
      setProposals([]);
      setReviewBaseMarkdown(null);
      setReviewSnapshot(null);
      clearReview();
      if (typeof window !== "undefined") {
        clearPendingMemoryReview(window.sessionStorage, classId, reviewStorageKey);
        markClassHomeTimelineRefresh(window.sessionStorage, classId);
      }
      router.refresh();
    } catch (e) {
      reportWorkflowError(e, "Commit failed");
    } finally {
      setLoading(false);
    }
  }, [
    artifactHash,
    artifactRevision,
    classId,
    clearWorkflowErrors,
    diaryMarkdown,
    draftId,
    getCommitPayload,
    clearReview,
    isUpdating,
    loading,
    commitResult,
    onError,
    reportWorkflowError,
    reviewStorageKey,
    router,
    runWithSessionRecovery,
    reviewSnapshot,
  ]);

  const keepAll = useCallback(() => {
    approveAll();
    void commit();
  }, [approveAll, commit]);

  const undoAll = useCallback(() => {
    setInReview(false);
    setEditingWiki(false);
    setProposals([]);
    setMemoryCandidates([]);
    setReviewBaseMarkdown(null);
    setReviewSnapshot(null);
    clearReview();
    if (typeof window !== "undefined") {
      clearPendingMemoryReview(window.sessionStorage, classId, reviewStorageKey);
    }
    clearWorkflowErrors();
  }, [classId, clearWorkflowErrors, clearReview, reviewStorageKey]);

  const draftPanel =
    inReview && editingWiki && selectedPath && selectedPath in contentByPath ? (
      <WikiProposalEditor
        wikiPath={selectedPath}
        markdown={contentByPath[selectedPath]}
        onChange={(value) => updateContent(selectedPath, value)}
      />
    ) : (
      <DiaryDraftPanel />
    );

  // Brief success, then auto-navigate home (no post-save preference / class cards).
  if (commitResult) {
    return (
      <div className="mx-auto flex w-full max-w-md min-h-0 flex-1 flex-col items-center justify-center gap-3 pb-8">
        <Card variant="highlight" ref={commitResultRef} className="w-full">
          <CardHeader>
            <CardTitle className="text-base">Memory saved</CardTitle>
            <p className="text-sm text-muted-foreground">
              {commitResult.title} ({commitResult.lesson_date}) —{" "}
              {commitResult.applied_wiki_paths.length} file
              {commitResult.applied_wiki_paths.length === 1 ? "" : "s"} updated.
            </p>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Returning to class home…
            </p>
            <Button variant="outline" size="sm" className="mt-3" asChild>
              <Link href={homeHrefAfterCommit}>Go now</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="shrink-0">
        <MemoryTargetStatus />
      </div>
      <ArtifactSessionWorkspace
        thread={
          <IngestThread
            activity={
              actionNeeded ||
              shouldShowReviewBrief({
                inReview,
                alreadyCommitted: !!commitResult,
                itemCount: reviewItems.length,
              }) ? (
                <div className="flex flex-col gap-2">
                  {actionNeeded ? (
                    <WorkflowActionNeededCard
                      message={actionNeeded.message}
                      respondInChat={actionNeeded.respondInChat}
                    />
                  ) : null}
                  {shouldShowReviewBrief({
                    inReview,
                    alreadyCommitted: !!commitResult,
                    itemCount: reviewItems.length,
                  }) ? (
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
                  ) : null}
                </div>
              ) : null
            }
          />
        }
        draftPanel={draftPanel}
        footer={
          !inReview ? (
            <div className="flex min-w-0 flex-col gap-2">
              <div className="flex min-w-0 flex-wrap items-center gap-3">
                <ReadyToSaveButton
                  onReady={handleReadyToSave}
                  operation={loading ? "compiling" : discarding ? "discarding" : "idle"}
                  disabled={discarding}
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleDiscardDraft}
                  disabled={loading || discarding || isUpdating || !draftId}
                >
                  {discarding ? "Discarding..." : "Discard draft"}
                </Button>
              </div>
              {hasDraftMessage && !loading && !isUpdating && (
                <p className="text-xs text-muted-foreground">
                  Send or clear the draft message before preparing wiki updates.
                </p>
              )}
              {readyToSave && !loading && !hasDraftMessage && (
                <p className="text-xs text-primary">
                  All sections filled - compile and review wiki file changes before saving.
                </p>
              )}
            </div>
          ) : null
        }
        reviewDiff={
          inReview && editingWiki && selectedChange ? (
            <MarkdownLineDiff
              path={selectedChange.path}
              before={selectedChange.before}
              after={selectedChange.after}
              className="h-full min-h-0"
              onDismiss={() => setEditingWiki(false)}
            />
          ) : null
        }
      />

      {inReview && !hasLessonResultsApproved && (
        <p className="text-xs text-destructive">
          Keep the lesson results change selected to save this lesson to memory.
        </p>
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
  const discardRedirectHref = useMemo(
    () =>
      memoryDiscardRedirectHref({
        classId,
        hasTimelineHint: Boolean(startHint?.lesson_date),
      }),
    [classId, startHint],
  );

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
        draftId: draft.draft_id,
        artifactRevision: draft.artifact_revision,
        artifactHash: draft.artifact_hash,
        turnInProgress: draft.turn_in_progress,
        latestTurnComplete: draft.latest_turn_complete,
        initialMessages: draft.messages?.length ? draft.messages : session.messages,
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
      lessonDate={startHint?.lesson_date}
      lessonTitle={startHint?.lesson_title}
      renderBody={({ onError }: ArtifactSessionBodyProps) => (
        <MemoryWorkspace
          classId={classId}
          reviewStorageKey={reviewStorageKey}
          discardRedirectHref={discardRedirectHref}
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
