"use client";

import { useArtifactSession } from "@/components/assistant-ui/artifact-session-runtime";
import { Thread } from "@/components/assistant-ui/thread";
import { DiaryChecklist } from "@/components/klassenpilot/diary-checklist";

function IngestWelcomeChecklist() {
  const { completeness } = useArtifactSession();
  return <DiaryChecklist checklist={completeness} inline />;
}

export function IngestThread() {
  const { draftId, turnInProgress } = useArtifactSession();
  return (
    <Thread
      welcomeExtra={<IngestWelcomeChecklist />}
      composerStorageKey={draftId ? `kp:composer:${draftId}` : undefined}
      backgroundTurnInProgress={turnInProgress}
    />
  );
}
