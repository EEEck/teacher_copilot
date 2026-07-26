"use client";

import { useArtifactSession } from "@/components/assistant-ui/artifact-session-runtime";
import { Thread } from "@/components/assistant-ui/thread";
import { ThreadActivity } from "@/components/assistant-ui/thread-activity";
import { DiaryChecklist } from "@/components/klassenpilot/diary-checklist";
import type { ReactNode } from "react";

function IngestWelcomeChecklist() {
  const { completeness } = useArtifactSession();
  return <DiaryChecklist checklist={completeness} inline />;
}

/**
 * Update Memory thread. Pass stacked `ThreadActivity` children (action-needed
 * card, ReviewBrief) via `activity` — same pattern as PlanThread.
 */
export function IngestThread({ activity }: { activity?: ReactNode }) {
  const { draftId, turnInProgress } = useArtifactSession();
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <Thread
        welcomeExtra={<IngestWelcomeChecklist />}
        composerStorageKey={draftId ? `kp:composer:${draftId}` : undefined}
        backgroundTurnInProgress={turnInProgress}
        activity={activity ? <ThreadActivity>{activity}</ThreadActivity> : null}
      />
    </div>
  );
}
