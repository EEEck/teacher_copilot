"use client";

import type { ReactNode } from "react";

import { useArtifactSession } from "@/components/assistant-ui/artifact-session-runtime";
import { Thread } from "@/components/assistant-ui/thread";
import { ThreadActivity } from "@/components/assistant-ui/thread-activity";
import { PlanVerificationPanel } from "@/components/klassenpilot/plan-verification-card";
import { StagedMemoryBanner } from "@/components/klassenpilot/staged-memory-banner";

/**
 * Static welcome that mirrors the (working) memory thread: nothing is injected
 * into the runtime. We previously seeded a dynamic opening message via an
 * imperative `aui.thread().append()` which caused a re-render loop ("blinking"),
 * and showing it in the welcome made it vanish on the first send ("history
 * disappeared"). A plain static welcome avoids both and matches memory exactly.
 *
 * Save review (`ReviewBrief`) and plan verification share the same in-chat
 * `ThreadActivity` surface as Update Memory's save card.
 */
export function PlanThread({
  classId,
  activity,
}: {
  classId: string;
  /** Extra in-chat activity (e.g. Save lesson plan ReviewBrief), stacked under verification. */
  activity?: ReactNode;
}) {
  const {
    draftId,
    sessionId,
    artifactRevision,
    turnInProgress,
    memoryCandidates,
  } = useArtifactSession();

  const hasActivity = Boolean(activity);
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <StagedMemoryBanner candidateCount={memoryCandidates.length} />
      <div className="min-h-0 flex-1 overflow-hidden">
        <Thread
          composerStorageKey={draftId ? `kp:composer:${draftId}` : undefined}
          backgroundTurnInProgress={turnInProgress}
          activity={
            <ThreadActivity>
              <div className="flex flex-col gap-2">
                <PlanVerificationPanel
                  classId={classId}
                  sessionId={sessionId}
                  artifactRevision={artifactRevision}
                />
                {hasActivity ? activity : null}
              </div>
            </ThreadActivity>
          }
          showSuggestions={false}
          welcome={{
            title: "Plan your next lesson",
            subtitle:
              "Chat about goals and timing. I load class memory automatically. Use + to attach a worksheet or draft plan (.md or .txt).",
          }}
          welcomeExtra={
            <ul className="aui-thread-welcome-message-inner mt-4 list-disc space-y-1 pl-5 text-sm text-muted-foreground delay-100 duration-200">
              <li>I use last lesson, open loops, and misconceptions automatically.</li>
              <li>The plan draft on the right updates as we talk; you can edit it anytime.</li>
              <li>Click “Ready to save plan” when you want to attach it to a lesson date.</li>
            </ul>
          }
        />
      </div>
    </div>
  );
}
