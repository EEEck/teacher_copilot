"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useArtifactSession } from "@/components/assistant-ui/artifact-session-runtime";
import { PlanThread } from "@/components/assistant-ui/plan-thread";
import { ArtifactDraftPanel } from "@/components/klassenpilot/artifact-draft-panel";
import {
  ArtifactSessionPage,
  type ArtifactSessionBodyProps,
} from "@/components/klassenpilot/artifact-session-page";
import { ArtifactSessionWorkspace } from "@/components/klassenpilot/artifact-session-workspace";
import { fromPlanSave, ReviewBrief } from "@/components/klassenpilot/review";
import {
  MemorySignalsReview,
  ProposedMemoryUpdates,
  splitPostSaveMemoryCandidates,
} from "@/components/klassenpilot/proposed-memory-updates";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { client, type MemoryCandidate } from "@/lib/api";

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

function PlanSaveFooter({
  classId,
  onError,
  inReview,
  setInReview,
  lessonDate,
  setLessonDate,
  setBeforePlan,
}: {
  classId: string;
  onError: (message: string | null) => void;
  inReview: boolean;
  setInReview: (v: boolean) => void;
  lessonDate: string;
  setLessonDate: (v: string) => void;
  setBeforePlan: (v: string) => void;
}) {
  const { artifactMarkdown, isUpdating, readyToSave, runWithSessionRecovery } =
    useArtifactSession();
  const [loading, setLoading] = useState(false);

  const handleReady = useCallback(async () => {
    if (!lessonDate.trim()) {
      onError("Enter a lesson date (YYYY-MM-DD).");
      return;
    }
    setLoading(true);
    onError(null);
    try {
      await runWithSessionRecovery((sessionId) =>
        client.planUpdateDraft(classId, sessionId, artifactMarkdown),
      );
      const path = `wiki/classes/${classId}/lessons/${lessonDate.trim()}/lesson_plan.md`;
      try {
        const file = await client.getWikiFile(classId, path);
        setBeforePlan(file.markdown);
      } catch {
        setBeforePlan("");
      }
      setInReview(true);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not prepare save");
    } finally {
      setLoading(false);
    }
  }, [classId, artifactMarkdown, lessonDate, onError, runWithSessionRecovery, setBeforePlan, setInReview]);

  if (inReview) {
    return (
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="lesson-date-review">Lesson date</Label>
          <Input
            id="lesson-date-review"
            type="date"
            value={lessonDate}
            onChange={(e) => setLessonDate(e.target.value)}
            className="w-[180px]"
            disabled={loading}
          />
        </div>
        <Button variant="ghost" onClick={() => setInReview(false)} disabled={loading}>
          Back
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="lesson-date">Lesson date</Label>
          <Input
            id="lesson-date"
            type="date"
            value={lessonDate}
            onChange={(e) => setLessonDate(e.target.value)}
            className="w-[180px]"
          />
        </div>
        <Button className="w-fit" onClick={handleReady} disabled={loading || isUpdating}>
          {loading ? "Preparing save…" : "Ready to save plan"}
        </Button>
      </div>
      {readyToSave && (
        <p className="text-xs text-primary">
          Plan looks complete — pick a date, then review changes before saving.
        </p>
      )}
    </div>
  );
}

function PlanWorkspace({
  classId,
  onError,
}: {
  classId: string;
  onError: (message: string | null) => void;
}) {
  const router = useRouter();
  const { artifactMarkdown, runWithSessionRecovery } = useArtifactSession();
  const [inReview, setInReview] = useState(false);
  const [lessonDate, setLessonDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [beforePlan, setBeforePlan] = useState("");
  const [approved, setApproved] = useState(true);
  const [loading, setLoading] = useState(false);
  const [proposedMemory, setProposedMemory] = useState<MemoryCandidate[] | null>(null);
  const [memorySignals, setMemorySignals] = useState<MemoryCandidate[] | null>(null);
  const [applyingMemory, setApplyingMemory] = useState(false);
  const [savingSignals, setSavingSignals] = useState(false);

  const goToLesson = useCallback(() => {
    router.push(`/classes/${classId}/lessons/${encodeURIComponent(lessonDate.trim())}`);
  }, [router, classId, lessonDate]);

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
            candidate_ids: c.candidate_id ? [c.candidate_id] : [],
          })),
        );
        goToLesson();
      } catch (e) {
        onError(e instanceof Error ? e.message : "Could not apply memory updates");
      } finally {
        setApplyingMemory(false);
      }
    },
    [classId, onError, goToLesson],
  );

  const continueAfterSignals = useCallback(
    async (_kept: MemoryCandidate[], removed: MemoryCandidate[]) => {
      setSavingSignals(true);
      onError(null);
      try {
        await Promise.all(
          removed
            .filter((candidate) => candidate.candidate_id)
            .map((candidate) =>
              client.memoryCandidateStatus(
                classId,
                candidate.candidate_id as string,
                "deleted",
                "Teacher removed this post-save signal.",
              ),
            ),
        );
        goToLesson();
      } catch (e) {
        onError(e instanceof Error ? e.message : "Could not update memory signals");
      } finally {
        setSavingSignals(false);
      }
    },
    [classId, onError, goToLesson],
  );

  const fileItem = useMemo(() => {
    if (!inReview || !lessonDate.trim()) return null;
    return fromPlanSave(classId, lessonDate.trim(), beforePlan, artifactMarkdown, approved);
  }, [inReview, classId, lessonDate, beforePlan, artifactMarkdown, approved]);

  const savePlan = useCallback(async () => {
    if (!approved || !lessonDate.trim()) return;
    setLoading(true);
    onError(null);
    try {
      const res = await runWithSessionRecovery((sessionId) =>
        client.planSave(classId, sessionId, lessonDate.trim(), artifactMarkdown),
      );
      const candidates = dedupeMemoryCandidates(res?.memory_candidates ?? []);
      const split = splitPostSaveMemoryCandidates(candidates);
      if (split.immediate.length) {
        setProposedMemory(split.immediate);
      } else if (split.signals.length) {
        setMemorySignals(split.signals);
      } else {
        goToLesson();
      }
    } catch (e) {
      onError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setLoading(false);
    }
  }, [approved, lessonDate, classId, artifactMarkdown, onError, goToLesson, runWithSessionRecovery]);

  useEffect(() => {
    if (!inReview || !lessonDate.trim()) return;
    const path = `wiki/classes/${classId}/lessons/${lessonDate.trim()}/lesson_plan.md`;
    let cancelled = false;
    void client.getWikiFile(classId, path).then(
      (file) => {
        if (!cancelled) setBeforePlan(file.markdown);
      },
      () => {
        if (!cancelled) setBeforePlan("");
      },
    );
    return () => {
      cancelled = true;
    };
  }, [inReview, classId, lessonDate]);

  if (proposedMemory) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 p-4">
        <p className="text-sm text-muted-foreground">
          Lesson plan saved for {lessonDate.trim()}.
        </p>
        <ProposedMemoryUpdates
          candidates={proposedMemory}
          onApply={applyMemory}
          applying={applyingMemory}
          onContinue={goToLesson}
          continueLabel="Skip and continue"
        />
      </div>
    );
  }

  if (memorySignals) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 p-4">
        <p className="text-sm text-muted-foreground">
          Lesson plan saved for {lessonDate.trim()}.
        </p>
        <MemorySignalsReview
          candidates={memorySignals}
          saving={savingSignals}
          onContinue={continueAfterSignals}
        />
      </div>
    );
  }

  return (
    <ArtifactSessionWorkspace
      thread={<PlanThread />}
      draftPanel={
        <ArtifactDraftPanel
          title="Lesson plan"
          placeholder="Your lesson plan will build here as you chat, or type directly…"
          updatingLabel="Updating plan from chat…"
        />
      }
      footer={
        <PlanSaveFooter
          classId={classId}
          onError={onError}
          inReview={inReview}
          setInReview={setInReview}
          lessonDate={lessonDate}
          setLessonDate={setLessonDate}
          setBeforePlan={setBeforePlan}
        />
      }
      reviewFileList={
        inReview && fileItem ? (
          <ReviewBrief
            items={[fileItem]}
            selectedPath={fileItem.path}
            title="Save lesson plan"
            onSetApproved={(_, v) => setApproved(v)}
            onUndoAll={() => setInReview(false)}
            onKeepAll={() => {
              setApproved(true);
              void savePlan();
            }}
            onSave={savePlan}
            saving={loading}
            saveDisabled={!approved}
          />
        ) : null
      }
    />
  );
}

export default function PlanPage() {
  const params = useParams();
  const classId = params.classId as string;

  const bootstrap = useCallback(
    async (opts?: { preserveMarkdown?: string }) => {
      const session = await client.startPlanSession(classId);
      let draft = await client.planGetDraft(classId, session.session_id);
      if (opts?.preserveMarkdown) {
        await client.planUpdateDraft(classId, session.session_id, opts.preserveMarkdown);
        draft = await client.planGetDraft(classId, session.session_id);
      }
      return {
        sessionId: session.session_id,
        initialMarkdown: draft.plan_markdown,
        openingMessage: session.opening_message,
      };
    },
    [classId],
  );

  return (
    <ArtifactSessionPage
      mode="plan"
      classId={classId}
      title="Create lesson plan"
      description="Chat to plan the next lesson, refine the draft on the right, then save to a lesson date."
      bootstrap={bootstrap}
      renderBody={({ onError }: ArtifactSessionBodyProps) => (
        <PlanWorkspace classId={classId} onError={onError} />
      )}
    />
  );
}
