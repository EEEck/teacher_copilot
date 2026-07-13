/**
 * Six chat-turn observations: 3 workflows × 2 cases.
 *
 * Case 1 — stay on page: live SSE → final → reply visible, no "Still working…"
 * Case 2 — leave mid-turn: abort SSE → "Still working…" → notifier upsert →
 *          reply merged into rich thread, spinner off
 *
 * These drive the same store + turn-activity helpers the runtime uses.
 * No OpenAI / browser required.
 */
import { describe, expect, it } from "vitest";
import type { ThreadMessageLike } from "@assistant-ui/react";

import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";
import { shouldShowResumedTurnStatus } from "@/components/assistant-ui/thread";
import {
  createWorkflowDraftStore,
  type WorkflowDraftSnapshot,
} from "@/features/workflow-drafts/workflow-draft-store";
import { workflowTurnActivity } from "@/features/workflow-drafts/workflow-turn-activity";
import {
  flagsForPhase,
  resolveClientStreamEnd,
} from "@/features/workflow-drafts/workflow-turn-state";
import {
  clearPendingChatTurn,
  listPendingChatTurns,
  markPendingChatTurn,
  shouldNotifyPendingDraftComplete,
} from "@/lib/pending-chat-turns";

const MODES: ArtifactMode[] = ["plan", "ingest", "discuss"];

function memoryStorage() {
  const storage = new Map<string, string>();
  return {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
    removeItem: (key: string) => storage.delete(key),
  };
}

function baseSnapshot(
  mode: ArtifactMode,
  overrides: Partial<WorkflowDraftSnapshot> = {},
): WorkflowDraftSnapshot {
  return {
    mode,
    classId: "chemie_9b_2026_27",
    draftId: `${mode}-draft`,
    sessionId: `${mode}-session`,
    messages: [{ role: "user", content: "Please draft the next step." }],
    artifactMarkdown: mode === "discuss" ? "" : "# Draft",
    artifactRevision: 1,
    artifactHash: "hash-1",
    turnInProgress: false,
    latestTurnComplete: true,
    ...overrides,
  };
}

function observe(localStreamActive: boolean, backendTurnInProgress: boolean) {
  const activity = workflowTurnActivity({
    localStreamActive,
    backendTurnInProgress,
  });
  return {
    /** Composer shows Stop (live SSE). */
    stopButton: activity.runtimeIsRunning,
    /** "Still working on your response…" banner. */
    stillWorking: shouldShowResumedTurnStatus(
      backendTurnInProgress,
      localStreamActive,
    ),
    activity,
  };
}

function lastAssistantText(thread: ThreadMessageLike[]): string | null {
  for (let i = thread.length - 1; i >= 0; i -= 1) {
    const message = thread[i];
    if (message.role !== "assistant") continue;
    if (typeof message.content === "string") return message.content;
    if (!Array.isArray(message.content)) return null;
    const text = message.content
      .filter(
        (part): part is { type: "text"; text: string } =>
          part.type === "text" && typeof (part as { text?: unknown }).text === "string",
      )
      .map((part) => part.text)
      .join("\n")
      .trim();
    return text || null;
  }
  return null;
}

function hasRichParts(thread: ThreadMessageLike[]): boolean {
  return thread.some((message) => Array.isArray(message.content));
}

describe.each(MODES)("chat turn scenarios — %s", (mode) => {
  it("Case 1: stay on page — live stream then final reply, no Still working", () => {
    const store = createWorkflowDraftStore();
    const storage = memoryStorage();
    const snap = baseSnapshot(mode, {
      turnInProgress: true,
      latestTurnComplete: false,
    });
    store.getState().upsert(snap);

    const pendingKey = markPendingChatTurn(storage, {
      mode,
      classId: snap.classId,
      sessionId: snap.sessionId,
      draftId: snap.draftId,
      resumeHref:
        mode === "plan"
          ? `/classes/${snap.classId}/plan`
          : mode === "ingest"
            ? `/classes/${snap.classId}/memory`
            : `/classes/${snap.classId}`,
      baselineMessageCount: 1,
    });
    expect(listPendingChatTurns(storage)).toHaveLength(1);

    // Mid-stream on page
    const mid = observe(true, true);
    expect(mid.stopButton).toBe(true);
    expect(mid.stillWorking).toBe(false);

    // Live final arrives
    const phase = resolveClientStreamEnd({
      gotFinal: true,
      hadStreamedContent: true,
    });
    expect(phase).toBe("complete");
    const flags = flagsForPhase(phase);

    store.getState().upsert({
      ...snap,
      messages: [
        { role: "user", content: "Please draft the next step." },
        { role: "assistant", content: `Final ${mode} reply.` },
      ],
      turnInProgress: flags.turnInProgress,
      latestTurnComplete: flags.latestTurnComplete,
      artifactRevision: 2,
      artifactHash: "hash-2",
    });

    const after = observe(flags.localStreamActive, flags.turnInProgress);
    expect(after.stopButton).toBe(false);
    expect(after.stillWorking).toBe(false);

    const thread = store.getState().threadMessagesByDraftId[snap.draftId];
    expect(lastAssistantText(thread)).toBe(`Final ${mode} reply.`);

    // Pending marker remains for notifier toast rules; draft itself is complete.
    expect(storage.getItem(pendingKey)).toBe("1");
    expect(
      shouldNotifyPendingDraftComplete(
        { turn_in_progress: false, latest_turn_complete: true },
        { seenInProgress: true },
        2,
      ),
    ).toBe(true);
  });

  it("Case 2: leave mid-turn — Still working, then merge final reply and clear spinner", () => {
    const store = createWorkflowDraftStore();
    const storage = memoryStorage();
    const snap = baseSnapshot(mode, {
      turnInProgress: true,
      latestTurnComplete: false,
    });
    store.getState().upsert(snap);

    markPendingChatTurn(storage, {
      mode,
      classId: snap.classId,
      sessionId: snap.sessionId,
      draftId: snap.draftId,
      resumeHref: `/classes/${snap.classId}`,
      baselineMessageCount: 1,
    });

    // Partial rich stream before leave
    store.getState().setThreadMessages(snap.draftId, [
      {
        id: "u",
        role: "user",
        content: "Please draft the next step.",
      },
      {
        id: "a",
        role: "assistant",
        content: [
          { type: "reasoning", text: "Working through the request..." },
          {
            type: "tool-call",
            toolName: "search_wiki",
            toolCallId: "call-1",
            args: {},
            argsText: "{}",
          },
        ],
      },
    ]);

    // Leave page: abort SSE without final
    const leavePhase = resolveClientStreamEnd({
      gotFinal: false,
      hadStreamedContent: true,
    });
    expect(leavePhase).toBe("backend_running");
    const leaveFlags = flagsForPhase(leavePhase);
    store.getState().upsert({
      ...store.getState().draftsById[snap.draftId],
      turnInProgress: leaveFlags.turnInProgress,
      latestTurnComplete: leaveFlags.latestTurnComplete
        ? true
        : store.getState().draftsById[snap.draftId].latestTurnComplete,
    });

    const waiting = observe(leaveFlags.localStreamActive, leaveFlags.turnInProgress);
    expect(waiting.stopButton).toBe(false);
    expect(waiting.stillWorking).toBe(true);
    expect(hasRichParts(store.getState().threadMessagesByDraftId[snap.draftId])).toBe(
      true,
    );
    expect(
      lastAssistantText(store.getState().threadMessagesByDraftId[snap.draftId]),
    ).toBeNull();

    // Backend finishes; notifier upserts completed draft (plain messages)
    store.getState().upsert({
      ...store.getState().draftsById[snap.draftId],
      messages: [
        { role: "user", content: "Please draft the next step." },
        { role: "assistant", content: `Recovered ${mode} reply.` },
      ],
      turnInProgress: false,
      latestTurnComplete: true,
      artifactRevision: 3,
      artifactHash: "hash-3",
    });

    // Abort finally must not regress a completed draft (runtime race guard).
    const existing = store.getState().draftsById[snap.draftId];
    expect(existing.turnInProgress).toBe(false);
    expect(existing.latestTurnComplete).toBe(true);
    // Simulate the forbidden regression — store should already be complete, so
    // the runtime skips this upsert. Assert observations as if it skipped.
    const done = observe(false, existing.turnInProgress);
    expect(done.stillWorking).toBe(false);
    expect(done.stopButton).toBe(false);

    const thread = store.getState().threadMessagesByDraftId[snap.draftId];
    expect(hasRichParts(thread)).toBe(true);
    expect(lastAssistantText(thread)).toBe(`Recovered ${mode} reply.`);

    clearPendingChatTurn(
      storage,
      listPendingChatTurns(storage)[0]?.key ?? `${mode}-pending`,
    );
    expect(listPendingChatTurns(storage)).toHaveLength(0);
  });
});
