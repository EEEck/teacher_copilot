"use client";

import { useParams, useRouter } from "next/navigation";
import { LoaderCircleIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useArtifactSession } from "@/components/assistant-ui/artifact-session-runtime";
import { PlanThread } from "@/components/assistant-ui/plan-thread";
import { ArtifactDraftPanel } from "@/components/klassenpilot/artifact-draft-panel";
import {
  ArtifactSessionPage,
  type ArtifactSessionBodyProps,
} from "@/components/klassenpilot/artifact-session-page";
import { ArtifactSessionWorkspace } from "@/components/klassenpilot/artifact-session-workspace";
import { PlanSaveConfirm } from "@/components/klassenpilot/plan-save-confirm";
import { WorkflowActionNeededCard } from "@/components/klassenpilot/workflow";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { client, type PlanMaterialSummary } from "@/lib/api";
import {
  classifyWorkflowError,
  routeWorkflowError,
} from "@/lib/workflow-error";
import { useWorkflowDraftStore } from "@/features/workflow-drafts/workflow-draft-store";

function PlanSaveFooter({
  classId,
  onError,
  reportWorkflowError,
  clearWorkflowErrors,
  inReview,
  setInReview,
  lessonDate,
  setLessonDate,
  onConfirmSave,
  saving,
}: {
  classId: string;
  onError: (message: string | null) => void;
  reportWorkflowError: (error: unknown, fallback: string) => void;
  clearWorkflowErrors: () => void;
  inReview: boolean;
  setInReview: (v: boolean) => void;
  lessonDate: string;
  setLessonDate: (v: string) => void;
  onConfirmSave: () => void;
  saving: boolean;
}) {
  const {
    artifactMarkdown,
    draftId,
    isUpdating,
    readyToSave,
    runWithSessionRecovery,
  } =
    useArtifactSession();
  const [operation, setOperation] = useState<"idle" | "preparing" | "discarding">("idle");
  const busy = operation !== "idle";

  const handleReady = useCallback(async () => {
    if (!lessonDate.trim()) {
      onError("Enter a lesson date (YYYY-MM-DD).");
      return;
    }
    setOperation("preparing");
    clearWorkflowErrors();
    try {
      await runWithSessionRecovery((sessionId) =>
        client.planUpdateDraft(classId, sessionId, artifactMarkdown),
      );
      setInReview(true);
    } catch (e) {
      reportWorkflowError(e, "Could not prepare save");
    } finally {
      setOperation("idle");
    }
  }, [
    classId,
    artifactMarkdown,
    lessonDate,
    onError,
    clearWorkflowErrors,
    reportWorkflowError,
    runWithSessionRecovery,
    setInReview,
  ]);

  const handleDiscard = useCallback(async () => {
    if (!draftId) return;
    setOperation("discarding");
    clearWorkflowErrors();
    try {
      await client.discardWorkflowDraft(classId, draftId);
      useWorkflowDraftStore.getState().remove(draftId);
      if (typeof window !== "undefined") {
        window.sessionStorage.removeItem(`kp:composer:${draftId}`);
        window.location.reload();
      }
    } catch (e) {
      reportWorkflowError(e, "Could not discard draft");
      setOperation("idle");
    }
  }, [classId, draftId, clearWorkflowErrors, reportWorkflowError]);

  if (inReview) {
    return (
      <PlanSaveConfirm
        lessonDate={lessonDate}
        onLessonDateChange={setLessonDate}
        onConfirm={onConfirmSave}
        onCancel={() => setInReview(false)}
        saving={saving}
      />
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
        <Button
          className="w-fit"
          onClick={handleReady}
          disabled={busy || isUpdating || !artifactMarkdown.trim()}
        >
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
          Plan looks complete — pick a date, then confirm save.
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
    sessionId,
    artifactRevision,
    artifactHash,
    runWithSessionRecovery,
  } = useArtifactSession();
  const [inReview, setInReview] = useState(false);
  const [loading, setLoading] = useState(false);
  const [materials, setMaterials] = useState<PlanMaterialSummary[]>([]);
  const [actionNeeded, setActionNeeded] = useState<{
    message: string;
    respondInChat: boolean;
  } | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    const refresh = () => {
      void client.planGetDraft(classId, sessionId).then((draft) => {
        if (!cancelled) setMaterials(draft.materials ?? []);
      }).catch(() => {
        /* draft hydrate is best-effort */
      });
    };
    refresh();
    const onUpdated = () => refresh();
    window.addEventListener("kp:plan-materials-updated", onUpdated);
    return () => {
      cancelled = true;
      window.removeEventListener("kp:plan-materials-updated", onUpdated);
    };
  }, [classId, sessionId]);

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

  const goToLesson = useCallback(() => {
    router.push(`/classes/${classId}/lessons/${encodeURIComponent(lessonDate.trim())}`);
  }, [router, classId, lessonDate]);

  const savePlan = useCallback(async () => {
    if (!lessonDate.trim()) return;
    setLoading(true);
    clearWorkflowErrors();
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
      reportWorkflowError(e, "Save failed");
      setLoading(false);
    }
  }, [
    lessonDate,
    classId,
    artifactMarkdown,
    draftId,
    artifactRevision,
    artifactHash,
    clearWorkflowErrors,
    reportWorkflowError,
    goToLesson,
    runWithSessionRecovery,
  ]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ArtifactSessionWorkspace
        thread={
          <PlanThread
            classId={classId}
            activity={
              actionNeeded ? (
                <WorkflowActionNeededCard
                  message={actionNeeded.message}
                  respondInChat={actionNeeded.respondInChat}
                />
              ) : null
            }
          />
        }
        draftPanel={
          <ArtifactDraftPanel
            title="Lesson plan"
            emptyPreviewFallback={
              "## Ready to build a lesson plan\n\n"
              + "Describe the topic, starting point, and constraints in chat. "
              + "I will create one shared package for the teacher, students, and lesson follow-up."
            }
            placeholder="Your lesson plan will build here as you chat, or type directly…"
            updatingLabel="Updating plan from chat…"
          />
        }
        footer={
          <div className="flex flex-col gap-2">
            {materials.length > 0 ? (
              <p className="text-xs text-muted-foreground">
                {materials.length} material{materials.length === 1 ? "" : "s"} will be
                kept with this lesson on save.
              </p>
            ) : null}
            <PlanSaveFooter
              classId={classId}
              onError={onError}
              reportWorkflowError={reportWorkflowError}
              clearWorkflowErrors={clearWorkflowErrors}
              inReview={inReview}
              setInReview={setInReview}
              lessonDate={lessonDate}
              setLessonDate={setLessonDate}
              onConfirmSave={() => {
                void savePlan();
              }}
              saving={loading}
            />
          </div>
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
