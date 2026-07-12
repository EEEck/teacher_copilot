import { describe, expect, it } from "vitest";

import {
  clearPendingChatTurn,
  clearPendingMemorySweep,
  consumeCompletedPendingChatTurn,
  dismissRunningTasksBox,
  isPendingDraftComplete,
  isPendingMemorySweepComplete,
  isRunningTasksBoxDismissed,
  listPendingChatTurns,
  markPendingChatTurn,
  markPendingMemorySweep,
  pendingMemorySweepKey,
  pendingTurnWorkflowHref,
  pendingTurnKey,
} from "./pending-chat-turns";

describe("pending chat turns", () => {
  it("treats completed backend draft status as notification-ready", () => {
    expect(
      isPendingDraftComplete({
        latest_turn_complete: true,
        turn_in_progress: false,
      }),
    ).toBe(true);
    expect(
      isPendingDraftComplete({
        latest_turn_complete: true,
        turn_in_progress: true,
      }),
    ).toBe(false);
    expect(isPendingDraftComplete({ latest_turn_complete: false })).toBe(false);
  });

  it("registers discoverable pending turns and clears them by key", () => {
    const storage = new Map<string, string>();
    const adapter = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
    };

    const key = markPendingChatTurn(adapter, {
      mode: "plan",
      classId: "chemie_9b_2026_27",
      sessionId: "session-1",
      draftId: "draft-1",
    });

    expect(key).toBe(pendingTurnKey("draft-1", "session-1"));
    expect(storage.get(key)).toBe("1");
    expect(listPendingChatTurns(adapter)).toEqual([
      {
        key,
        mode: "plan",
        classId: "chemie_9b_2026_27",
        sessionId: "session-1",
        draftId: "draft-1",
      },
    ]);

    clearPendingChatTurn(adapter, key);

    expect(storage.has(key)).toBe(false);
    expect(listPendingChatTurns(adapter)).toEqual([]);
  });

  it("lets exactly one UI surface consume a completed turn notification", () => {
    const storage = new Map<string, string>();
    const adapter = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
    };
    const key = markPendingChatTurn(adapter, {
      mode: "ingest",
      classId: "chemie_9b_2026_27",
      sessionId: "session-1",
      draftId: "draft-1",
    });

    expect(consumeCompletedPendingChatTurn(adapter, key)).toBe(true);
    expect(consumeCompletedPendingChatTurn(adapter, key)).toBe(false);
  });

  it("round-trips optional lesson metadata on pending turns", () => {
    const storage = new Map<string, string>();
    const adapter = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
    };

    markPendingChatTurn(adapter, {
      mode: "ingest",
      classId: "chemie_9b_2026_27",
      sessionId: "session-1",
      draftId: "draft-1",
      lessonDate: "2026-07-10",
      lessonTitle: "Ions review",
      resumeHref:
        "/classes/chemie_9b_2026_27/memory?lessonDate=2026-07-10&intent=update_missing_results&targetKind=planned_lesson",
    });

    expect(listPendingChatTurns(adapter)).toEqual([
      {
        key: pendingTurnKey("draft-1", "session-1"),
        mode: "ingest",
        classId: "chemie_9b_2026_27",
        sessionId: "session-1",
        draftId: "draft-1",
        lessonDate: "2026-07-10",
        lessonTitle: "Ions review",
        resumeHref:
          "/classes/chemie_9b_2026_27/memory?lessonDate=2026-07-10&intent=update_missing_results&targetKind=planned_lesson",
      },
    ]);
  });

  it("returns a pending timeline turn to its original workflow URL", () => {
    const turn = {
      key: "kp:turn-pending:draft-1",
      mode: "ingest" as const,
      classId: "chemie_9b_2026_27",
      sessionId: "session-1",
      draftId: "draft-1",
      resumeHref:
        "/classes/chemie_9b_2026_27/memory?lessonDate=2026-07-10&intent=update_missing_results&targetKind=planned_lesson",
    };

    expect(pendingTurnWorkflowHref(turn)).toBe(turn.resumeHref);
    expect(
      pendingTurnWorkflowHref({ ...turn, resumeHref: "/classes/other/memory" }),
    ).toBe("/classes/chemie_9b_2026_27/memory");
  });

  it("hides the running-tasks box for the current key set until a new turn appears", () => {
    const storage = new Map<string, string>();
    const adapter = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
    };

    markPendingChatTurn(adapter, {
      mode: "plan",
      classId: "chemie_9b_2026_27",
      sessionId: "session-1",
      draftId: "draft-1",
      lessonDate: "2026-07-10",
    });
    const first = listPendingChatTurns(adapter);
    expect(isRunningTasksBoxDismissed(adapter, first)).toBe(false);

    dismissRunningTasksBox(adapter, first);
    expect(isRunningTasksBoxDismissed(adapter, first)).toBe(true);

    markPendingChatTurn(adapter, {
      mode: "ingest",
      classId: "chemie_9b_2026_27",
      sessionId: "session-2",
      draftId: "draft-2",
      lessonTitle: "Acids",
    });
    expect(isRunningTasksBoxDismissed(adapter, listPendingChatTurns(adapter))).toBe(
      false,
    );
  });

  it("tracks one Memory Sweep job per class with the sweep workflow href", () => {
    const storage = new Map<string, string>();
    const adapter = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
    };

    const key = markPendingMemorySweep(adapter, {
      classId: "chemie_9b_2026_27",
      reviewId: "review-1",
    });
    expect(key).toBe(pendingMemorySweepKey("chemie_9b_2026_27"));
    const turns = listPendingChatTurns(adapter);
    expect(turns).toEqual([
      {
        key,
        mode: "memory_sweep",
        classId: "chemie_9b_2026_27",
        sessionId: "review-1",
        draftId: "review-1",
        resumeHref: "/classes/chemie_9b_2026_27/memory-sweep",
      },
    ]);
    expect(pendingTurnWorkflowHref(turns[0])).toBe(
      "/classes/chemie_9b_2026_27/memory-sweep",
    );

    markPendingMemorySweep(adapter, {
      classId: "chemie_9b_2026_27",
      reviewId: "review-2",
    });
    expect(listPendingChatTurns(adapter)).toHaveLength(1);
    expect(listPendingChatTurns(adapter)[0].sessionId).toBe("review-2");

    clearPendingMemorySweep(adapter, "chemie_9b_2026_27");
    expect(listPendingChatTurns(adapter)).toEqual([]);
  });

  it("treats Memory Sweep reviews as complete once generation finishes", () => {
    expect(isPendingMemorySweepComplete({ status: "generating" })).toBe(false);
    expect(isPendingMemorySweepComplete({ status: "ready" })).toBe(true);
    expect(isPendingMemorySweepComplete({ status: "failed" })).toBe(true);
    expect(isPendingMemorySweepComplete({ status: "stale" })).toBe(true);
  });
});
