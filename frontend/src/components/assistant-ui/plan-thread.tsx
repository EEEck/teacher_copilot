"use client";

import type { ReactNode } from "react";

import { useArtifactSession } from "@/components/assistant-ui/artifact-session-runtime";
import { Thread } from "@/components/assistant-ui/thread";
import { ThreadActivity } from "@/components/assistant-ui/thread-activity";
import { PlanAttachProvider } from "@/components/klassenpilot/plan-attach-dialog";
import { PlanVerificationPanel } from "@/components/klassenpilot/plan-verification-card";
import { StagedMemoryBanner } from "@/components/klassenpilot/staged-memory-banner";

/**
 * Static welcome that mirrors the (working) memory thread: nothing is injected
 * into the runtime. We previously seeded a dynamic opening message via an
 * imperative `aui.thread().append()` which caused a re-render loop ("blinking"),
 * and showing it in the welcome made it vanish on the first send ("history
 * disappeared"). A plain static welcome avoids both and matches memory exactly.
 *
 * Plan verification and workflow action-needed cards stay in-chat via
 * `ThreadActivity`. Plan save confirm lives in the footer.
 *
 * Class PDFs: composer + opens PlanAttachDialog (Textbook/Personal + drag/browse);
 * drop/paste PDF on the composer opens the same dialog with the file staged.
 */
export function PlanThread({
  classId,
  activity,
}: {
  classId: string;
  /** Optional extra in-chat activity stacked under verification. */
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
        <PlanAttachProvider>
          <Thread
            composerStorageKey={draftId ? `kp:composer:${draftId}` : undefined}
            backgroundTurnInProgress={turnInProgress}
            addAttachmentTooltip="Attach PDF (class material) or .md / .txt notes"
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
                "Chat about goals and timing. I load class memory automatically. Use + (or drop a PDF) to attach a textbook or personal PDF.",
            }}
            welcomeExtra={
              <ul className="aui-thread-welcome-message-inner mt-4 list-disc space-y-1 pl-5 text-sm text-muted-foreground delay-100 duration-200">
                <li>I use last lesson, open loops, and misconceptions automatically.</li>
                <li>
                  Use + or drop a PDF to open the attach dialog — choose Textbook
                  or Personal; OCR continues on a composer tile (green check when
                  ready).
                </li>
                <li>The plan draft on the right updates as we talk; you can edit it anytime.</li>
                <li>Click “Ready to save plan” when you want to attach it to a lesson date.</li>
              </ul>
            }
          />
        </PlanAttachProvider>
      </div>
    </div>
  );
}
