import { describe, expect, it } from "vitest";

import {
  clearPendingChatTurn,
  isPendingDraftComplete,
  listPendingChatTurns,
  markPendingChatTurn,
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
});
