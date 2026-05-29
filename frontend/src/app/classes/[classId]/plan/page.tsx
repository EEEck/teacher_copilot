"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArtifactSessionWorkspace } from "@/components/klassenpilot/artifact-session-workspace";
import { ArtifactDraftPanel } from "@/components/klassenpilot/artifact-draft-panel";
import { PlanRuntimeProvider } from "@/components/assistant-ui/plan-runtime-provider";
import { PlanThread } from "@/components/assistant-ui/plan-thread";
import { useArtifactSession } from "@/components/assistant-ui/artifact-session-runtime";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { client, type PlanSession } from "@/lib/api";

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
      const result = await client.planSave(
        classId,
        sessionId,
        lessonDate.trim(),
        artifactMarkdown,
      );
      onDone(result.lesson_date);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Save failed");
    } finally {
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
          <Button onClick={handleSave} disabled={loading || isUpdating}>
            Save plan to lesson
          </Button>
          <Button variant="ghost" onClick={() => setShowSave(false)} disabled={loading}>
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

  const [session, setSession] = useState<PlanSession | null>(null);
  const [initialPlan, setInitialPlan] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await client.startPlanSession(classId);
        if (cancelled) return;
        setSession(s);
        const d = await client.planGetDraft(classId, s.session_id);
        if (cancelled) return;
        setInitialPlan(d.plan_markdown);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to start session");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [classId]);

  if (!session || !initialPlan) {
    return (
      <div>
        <PageHeader backHref={`/classes/${classId}`} backLabel="Class home" title="Create lesson plan" />
        {error ? (
          <Alert className="mb-6 border-destructive/30 bg-[var(--error-bg)] text-destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : (
          <p className="text-muted-foreground">Starting session…</p>
        )}
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        backHref={`/classes/${classId}`}
        backLabel="Class home"
        title="Create lesson plan"
        description="Chat to plan the next lesson, refine the draft on the right, then save to a lesson date."
      />

      {error && (
        <Alert className="mb-6 border-destructive/30 bg-[var(--error-bg)] text-destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <PlanRuntimeProvider
        classId={classId}
        sessionId={session.session_id}
        initialPlanMarkdown={initialPlan}
      >
        <ArtifactSessionWorkspace
          thread={<PlanThread openingMessage={session.opening_message} />}
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
              sessionId={session.session_id}
              onError={setError}
              onDone={(lessonDate) => {
                router.push(`/classes/${classId}?highlight=${encodeURIComponent(lessonDate)}`);
                router.refresh();
              }}
            />
          }
        />
      </PlanRuntimeProvider>
    </div>
  );
}
