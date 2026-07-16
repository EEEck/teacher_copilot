"use client";

import { useParams, useRouter } from "next/navigation";
import { LoaderCircleIcon } from "lucide-react";
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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { client } from "@/lib/api";
import { errorMessageFromUnknown } from "@/lib/write-verification-error";
import { useWorkflowDraftStore } from "@/features/workflow-drafts/workflow-draft-store";

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
  const { artifactMarkdown, draftId, isUpdating, readyToSave, runWithSessionRecovery } =
    useArtifactSession();
  const [operation, setOperation] = useState<"idle" | "preparing" | "discarding">("idle");
  const busy = operation !== "idle";

  const handleReady = useCallback(async () => {
    if (!lessonDate.trim()) {
      onError("Enter a lesson date (YYYY-MM-DD).");
      return;
    }
    setOperation("preparing");
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
      setOperation("idle");
    }
  }, [classId, artifactMarkdown, lessonDate, onError, runWithSessionRecovery, setBeforePlan, setInReview]);

  const handleDiscard = useCallback(async () => {
    if (!draftId) return;
    setOperation("discarding");
    onError(null);
    try {
      await client.discardWorkflowDraft(classId, draftId);
      useWorkflowDraftStore.getState().remove(draftId);
      if (typeof window !== "undefined") {
        window.sessionStorage.removeItem(`kp:composer:${draftId}`);
        window.location.reload();
      }
    } catch (e) {
      onError(errorMessageFromUnknown(e, "Could not discard draft"));
      setOperation("idle");
    }
  }, [classId, draftId, onError]);

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
            disabled={busy}
          />
        </div>
        <Button variant="ghost" onClick={() => setInReview(false)} disabled={busy}>
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
        <Button className="w-fit" onClick={handleReady} disabled={busy || isUpdating}>
          {operation === "preparing" ? (
            <>
              <LoaderCircleIcon className="animate-spin" />
              Preparing save…
            </>
          ) : (
            "Ready to save plan"
          )}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={handleDiscard}
          disabled={busy || isUpdating || !draftId}
        >
          {operation === "discarding" ? (
            <>
              <LoaderCircleIcon className="animate-spin" />
              Discarding…
            </>
          ) : (
            "Discard draft"
          )}
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
  lessonDate,
  setLessonDate,
  onError,
}: {
  classId: string;
  lessonDate: string;
  setLessonDate: (value: string) => void;
  onError: (message: string | null) => void;
}) {
  const router = useRouter();
  const {
    artifactMarkdown,
    draftId,
    artifactRevision,
    artifactHash,
    runWithSessionRecovery,
  } = useArtifactSession();
  const [inReview, setInReview] = useState(false);
  const [beforePlan, setBeforePlan] = useState("");
  const [approved, setApproved] = useState(true);
  const [loading, setLoading] = useState(false);

  const goToLesson = useCallback(() => {
    router.push(`/classes/${classId}/lessons/${encodeURIComponent(lessonDate.trim())}`);
  }, [router, classId, lessonDate]);

  const fileItem = useMemo(() => {
    if (!inReview || !lessonDate.trim()) return null;
    return fromPlanSave(classId, lessonDate.trim(), beforePlan, artifactMarkdown, approved);
  }, [inReview, classId, lessonDate, beforePlan, artifactMarkdown, approved]);

  const savePlan = useCallback(async () => {
    if (!approved || !lessonDate.trim()) return;
    setLoading(true);
    onError(null);
    try {
      // Staged remember(...) candidates stay in the ledger for Memory Sweep;
      // do not surface a post-save preference / signal review screen.
      await runWithSessionRecovery((sessionId) =>
        client.planSave(classId, sessionId, lessonDate.trim(), artifactMarkdown, {
          draftId,
          expectedArtifactRevision: artifactRevision,
          expectedArtifactHash: artifactHash,
        }),
      );
      goToLesson();
    } catch (e) {
      onError(errorMessageFromUnknown(e, "Save failed"));
      setLoading(false);
    }
  }, [
    approved,
    lessonDate,
    classId,
    artifactMarkdown,
    draftId,
    artifactRevision,
    artifactHash,
    onError,
    goToLesson,
    runWithSessionRecovery,
  ]);

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

  return (
    <div className="flex min-h-0 flex-1 flex-col">
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
    </div>
  );
}

export default function PlanPage() {
  const params = useParams();
  const classId = params.classId as string;
  const [lessonDate, setLessonDate] = useState(() => new Date().toISOString().slice(0, 10));

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
        draftId: draft.draft_id,
        artifactRevision: draft.artifact_revision,
        artifactHash: draft.artifact_hash,
        turnInProgress: draft.turn_in_progress,
        latestTurnComplete: draft.latest_turn_complete,
        initialMessages: draft.messages?.length ? draft.messages : session.messages,
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
      lessonDate={lessonDate}
      renderBody={({ onError }: ArtifactSessionBodyProps) => (
        <PlanWorkspace
          classId={classId}
          lessonDate={lessonDate}
          setLessonDate={setLessonDate}
          onError={onError}
        />
      )}
    />
  );
}
