"use client";

import { useArtifactSession } from "@/components/assistant-ui/artifact-session-runtime";
import { Thread } from "@/components/assistant-ui/thread";

/**
 * Thin welcome wrapper over shared Thread — same pattern as PlanThread.
 * Parent must supply a height-filled flex shell (route workspace or DiscussDock).
 */
export function DiscussThread() {
  const { draftId, turnInProgress, memoryCandidates } = useArtifactSession();
  const candidateCount = memoryCandidates.length;
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      {candidateCount > 0 ? (
        <p className="shrink-0 border-b border-border bg-muted px-4 py-2 text-xs text-muted-foreground">
          {candidateCount} review-only memory candidate
          {candidateCount === 1 ? "" : "s"} staged this session. Wiki files are
          unchanged — review them in Memory Sweep when ready.
        </p>
      ) : null}
      <div className="h-full min-h-0 flex-1 overflow-hidden">
        <Thread
          composerStorageKey={draftId ? `kp:composer:${draftId}` : undefined}
          backgroundTurnInProgress={turnInProgress}
          showSuggestions={false}
          welcome={{
            title: "Discuss class state",
            subtitle:
              "Ask about open loops, misconceptions, recent lessons, or what to do next. This chat is read-only against the wiki.",
          }}
          welcomeExtra={
            <ul className="aui-thread-welcome-message-inner mt-4 list-disc space-y-1 pl-5 text-sm text-muted-foreground delay-100 duration-200">
              <li>I load teacher and class memory automatically.</li>
              <li>
                Durable facts can be staged for review — I never write the wiki
                here.
              </li>
              <li>
                Use Update memory or Create lesson plan when you need a saveable
                artifact.
              </li>
            </ul>
          }
        />
      </div>
    </div>
  );
}
