"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { useArtifactSession } from "@/components/assistant-ui/artifact-session-runtime";
import { PlanThread } from "@/components/assistant-ui/plan-thread";
import { ArtifactDraftPanel } from "@/components/klassenpilot/artifact-draft-panel";
import {
  ArtifactSessionPage,
  type ArtifactSessionBodyProps,
} from "@/components/klassenpilot/artifact-session-page";
import { ArtifactSessionWorkspace } from "@/components/klassenpilot/artifact-session-workspace";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { client } from "@/lib/api";

function ReadyToSavePlan({
  classId,
  sessionId,
  onError,
  onDone,
}: {
  classId: string;
  sessionId: string;
  onError: (message: string | null) => void;
  onDone: (lessonDate: string) => void;
}) {
  const { artifactMarkdown, isUpdating, readyToSave } = useArtifactSession();
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showSave, setShowSave] = useState(false);
  const [lessonDate, setLessonDate] = useState(() => new Date().toISOString().slice(0, 10));

  const handleReady = useCallback(async () => {
    setShowSave(true);
    onError(null);
    try {
      await client.planUpdateDraft(classId, sessionId, artifactMarkdown);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not sync draft");
    }
  }, [classId, sessionId, artifactMarkdown, onError]);

  const handleSave = useCallback(async () => {
    if (!lessonDate.trim()) {
      onError("Enter a lesson date (YYYY-MM-DD).");
      return;
    }
    setLoading(true);
    onError(null);
    try {
      const result = await client.planSave(classId, sessionId, lessonDate.trim(), artifactMarkdown);
      // Show a clear "Saved" confirmation before navigating to the saved lesson.
      setSaved(true);
      setLoading(false);
      setTimeout(() => onDone(result.lesson_date), 1500);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Save failed");
      setLoading(false);
    }
  }, [classId, sessionId, lessonDate, artifactMarkdown, onError, onDone]);

  return (
    <div className="flex flex-col gap-3">
      {!showSave ? (
        <div className="flex flex-col gap-1">
          <Button className="w-fit" onClick={handleReady} disabled={loading || isUpdating}>
            Ready to save plan
          </Button>
          {readyToSave && (
            <p className="text-xs text-primary">Plan looks complete — pick a lesson date to save.</p>
          )}
        </div>
      ) : (
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
          <Button onClick={handleSave} disabled={loading || saved || isUpdating}>
            {saved ? (
              <>
                <Check className="size-4" /> Saved — opening lesson…
              </>
            ) : loading ? (
              "Saving…"
            ) : (
              "Save plan to lesson"
            )}
          </Button>
          <Button variant="ghost" onClick={() => setShowSave(false)} disabled={loading || saved}>
            Back
          </Button>
        </div>
      )}
    </div>
  );
}

export default function PlanPage() {
  const params = useParams();
  const classId = params.classId as string;
  const router = useRouter();

  const bootstrap = useCallback(async () => {
    const session = await client.startPlanSession(classId);
    const draft = await client.planGetDraft(classId, session.session_id);
    return {
      sessionId: session.session_id,
      initialMarkdown: draft.plan_markdown,
      openingMessage: session.opening_message,
    };
  }, [classId]);

  return (
    <ArtifactSessionPage
      mode="plan"
      classId={classId}
      title="Create lesson plan"
      description="Chat to plan the next lesson, refine the draft on the right, then save to a lesson date."
      bootstrap={bootstrap}
      renderBody={({ sessionId, onError }: ArtifactSessionBodyProps) => (
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
            <ReadyToSavePlan
              classId={classId}
              sessionId={sessionId}
              onError={onError}
              onDone={(lessonDate) => {
                // Land on the saved lesson so the teacher immediately sees the plan persisted.
                router.push(`/classes/${classId}/lessons/${encodeURIComponent(lessonDate)}`);
              }}
            />
          }
        />
      )}
    />
  );
}
