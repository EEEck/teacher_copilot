import { describe, expect, it } from "vitest";

import { CHAT_ERROR_REPLY } from "./chat-errors";
import {
  createWorkflowDraftStore,
  mergeFinalReplyIntoThread,
  selectThreadMessages,
  type WorkflowDraftSnapshot,
} from "./workflow-draft-store";

function snapshot(
  overrides: Partial<WorkflowDraftSnapshot> = {},
): WorkflowDraftSnapshot {
  return {
    mode: "ingest",
    classId: "chemie_9b_2026_27",
    draftId: "draft-1",
    sessionId: "session-1",
    messages: [{ role: "user", content: "Record lesson results." }],
    artifactMarkdown: "# Lesson results",
    artifactRevision: 1,
    artifactHash: "hash-1",
    turnInProgress: true,
    latestTurnComplete: false,
    ...overrides,
  };
}

const RICH_THREAD = [
  { id: "u", role: "user" as const, content: "Record lesson results." },
  {
    id: "a",
    role: "assistant" as const,
    content: [
      { type: "reasoning" as const, text: "Reading class memory..." },
      {
        type: "tool-call" as const,
        toolName: "search",
        toolCallId: "t1",
        args: {},
        argsText: "{}",
      },
    ],
  },
];

function beginRichTurn(store: ReturnType<typeof createWorkflowDraftStore>) {
  store.getState().upsert(snapshot({ turnInProgress: false, latestTurnComplete: true }));
  store.getState().beginTurn("draft-1", {
    userContent: "Record lesson results.",
    placeholderContent: [{ type: "reasoning", text: "Starting..." }],
    pendingKey: "pending-1",
  });
  store
    .getState()
    .applyTurnProgress("draft-1", RICH_THREAD[1].content);
}

describe("selectThreadMessages (Bug A regression, invariant I6)", () => {
  it("returns the identical reference for a missing key across calls", () => {
    const store = createWorkflowDraftStore();
    const first = selectThreadMessages("missing")(store.getState());
    const second = selectThreadMessages("missing")(store.getState());
    expect(first).toBe(second);
    expect(first).toEqual([]);
  });
});

describe("snapshot reducer (design §A.1.4)", () => {
  it("no turn record → replaces the thread from snapshot messages", () => {
    const store = createWorkflowDraftStore();
    store.getState().upsert(
      snapshot({
        messages: [
          { role: "user", content: "Record lesson results." },
          { role: "assistant", content: "The lesson diary is ready." },
        ],
        turnInProgress: false,
        latestTurnComplete: true,
      }),
    );
    expect(store.getState().threadMessagesByDraftId["draft-1"]).toEqual([
      { id: "persisted-0", role: "user", content: "Record lesson results." },
      {
        id: "persisted-1",
        role: "assistant",
        content: "The lesson diary is ready.",
      },
    ]);
  });

  it("no turn record → an empty snapshot never wipes a non-empty thread", () => {
    const store = createWorkflowDraftStore();
    store.getState().upsert(snapshot());
    store.getState().upsert(snapshot({ messages: [], artifactRevision: 2 }));
    expect(store.getState().threadMessagesByDraftId["draft-1"]).toHaveLength(1);
    expect(store.getState().draftsById["draft-1"].artifactRevision).toBe(2);
  });

  it("streaming → snapshot upserts refresh the draft but never touch the thread", () => {
    const store = createWorkflowDraftStore();
    beginRichTurn(store);
    const before = store.getState().threadMessagesByDraftId["draft-1"];

    store.getState().upsert(
      snapshot({
        messages: [
          { role: "user", content: "Record lesson results." },
          { role: "assistant", content: "Flat persisted copy." },
        ],
        artifactRevision: 3,
      }),
    );

    expect(store.getState().threadMessagesByDraftId["draft-1"]).toBe(before);
    expect(store.getState().draftsById["draft-1"].artifactRevision).toBe(3);
    expect(store.getState().turnByDraftId["draft-1"].phase).toBe("streaming");
  });

  it("awaiting_backend + still in progress → thread untouched, phase kept", () => {
    const store = createWorkflowDraftStore();
    beginRichTurn(store);
    store.getState().markAwaitingBackend("draft-1");
    const before = store.getState().threadMessagesByDraftId["draft-1"];

    store.getState().upsert(
      snapshot({ turnInProgress: true, latestTurnComplete: false }),
    );

    expect(store.getState().threadMessagesByDraftId["draft-1"]).toBe(before);
    expect(store.getState().turnByDraftId["draft-1"].phase).toBe(
      "awaiting_backend",
    );
  });

  it("awaiting_backend + complete → merges the final reply into rich parts and settles", () => {
    const store = createWorkflowDraftStore();
    beginRichTurn(store);
    store.getState().markAwaitingBackend("draft-1");

    store.getState().upsert(
      snapshot({
        messages: [
          { role: "user", content: "Record lesson results." },
          { role: "assistant", content: "Here is the draft." },
        ],
        turnInProgress: false,
        latestTurnComplete: true,
      }),
    );

    const thread = store.getState().threadMessagesByDraftId["draft-1"];
    const assistant = thread[thread.length - 1];
    const parts = assistant.content as Array<{ type: string; text?: string }>;
    expect(parts.some((p) => p.type === "reasoning")).toBe(true);
    expect(parts.some((p) => p.type === "tool-call")).toBe(true);
    expect(
      parts.some((p) => p.type === "text" && p.text === "Here is the draft."),
    ).toBe(true);
    expect(store.getState().turnByDraftId["draft-1"].phase).toBe("settled");
  });

  it("awaiting_backend + interrupted → appends the error reply and settles", () => {
    const store = createWorkflowDraftStore();
    beginRichTurn(store);
    store.getState().markAwaitingBackend("draft-1");

    store.getState().upsert(
      snapshot({ turnInProgress: false, latestTurnComplete: false }),
    );

    const thread = store.getState().threadMessagesByDraftId["draft-1"];
    const parts = thread[thread.length - 1].content as Array<{
      type: string;
      text?: string;
    }>;
    expect(
      parts.some((p) => p.type === "text" && p.text === CHAT_ERROR_REPLY),
    ).toBe(true);
    expect(store.getState().turnByDraftId["draft-1"].phase).toBe("settled");
  });

  it("settled → the local thread stays authoritative against flat snapshots", () => {
    const store = createWorkflowDraftStore();
    beginRichTurn(store);
    store.getState().completeTurn("draft-1", {
      content: [
        { type: "reasoning", text: "Reading class memory..." },
        { type: "text", text: "Here is the draft." },
      ],
      reply: "Here is the draft.",
      userText: "Record lesson results.",
      artifactMarkdown: "# Updated",
      artifactRevision: 2,
      artifactHash: "hash-2",
    });
    const before = store.getState().threadMessagesByDraftId["draft-1"];

    // e.g. PendingTurnNotifier consuming the marker after completion.
    store.getState().upsert(
      snapshot({
        messages: [
          { role: "user", content: "Record lesson results." },
          { role: "assistant", content: "Here is the draft." },
        ],
        turnInProgress: false,
        latestTurnComplete: true,
        artifactRevision: 2,
        artifactHash: "hash-2",
      }),
    );

    expect(store.getState().threadMessagesByDraftId["draft-1"]).toBe(before);
    expect(store.getState().turnByDraftId["draft-1"].phase).toBe("settled");
  });

  it("GET-shaped upserts keep final-turn meta (undefined means unknown, not cleared)", () => {
    const store = createWorkflowDraftStore();
    beginRichTurn(store);
    store.getState().completeTurn("draft-1", {
      content: [{ type: "text", text: "Done." }],
      reply: "Done.",
      userText: "Record lesson results.",
      artifactMarkdown: "# Updated",
      readyToSave: true,
      lastChangeSummary: "Filled sections.",
      memoryCandidates: [{ target: "class_state.md", candidate_update: "x" }],
    });

    // Notifier/recovery polls upsert GET-draft snapshots, which never carry
    // final-turn meta fields.
    store.getState().upsert(
      snapshot({
        turnInProgress: false,
        latestTurnComplete: true,
        artifactRevision: 2,
      }),
    );

    const snap = store.getState().draftsById["draft-1"];
    expect(snap.readyToSave).toBe(true);
    expect(snap.lastChangeSummary).toBe("Filled sections.");
    expect(snap.memoryCandidates).toHaveLength(1);
    expect(snap.artifactRevision).toBe(2); // fields the snapshot carries still replace
  });
});

describe("turn actions", () => {
  it("beginTurn appends user + placeholder and sets streaming flags", () => {
    const store = createWorkflowDraftStore();
    store
      .getState()
      .upsert(snapshot({ turnInProgress: false, latestTurnComplete: true }));
    store.getState().beginTurn("draft-1", {
      userContent: "New note",
      placeholderContent: [{ type: "reasoning", text: "Starting..." }],
    });

    const thread = store.getState().threadMessagesByDraftId["draft-1"];
    expect(thread[thread.length - 2].role).toBe("user");
    expect(thread[thread.length - 1].role).toBe("assistant");
    expect(store.getState().draftsById["draft-1"].turnInProgress).toBe(true);
    expect(store.getState().draftsById["draft-1"].latestTurnComplete).toBe(false);
    expect(store.getState().turnByDraftId["draft-1"].phase).toBe("streaming");
  });

  it("turn actions no-op after the draft is removed (invariant I5)", () => {
    const store = createWorkflowDraftStore();
    beginRichTurn(store);
    store.getState().remove("draft-1");

    store.getState().applyTurnProgress("draft-1", [
      { type: "text", text: "late event" },
    ]);
    store.getState().completeTurn("draft-1", {
      content: [{ type: "text", text: "late final" }],
      reply: "late final",
      userText: "x",
      artifactMarkdown: "# Late",
    });
    store.getState().failTurn("draft-1", "late failure");
    store.getState().markAwaitingBackend("draft-1");

    expect(store.getState().draftsById["draft-1"]).toBeUndefined();
    expect(store.getState().threadMessagesByDraftId["draft-1"]).toBeUndefined();
    expect(store.getState().turnByDraftId["draft-1"]).toBeUndefined();
  });

  it("completeTurn writes reply, artifact, meta, message mirror, and settles", () => {
    const store = createWorkflowDraftStore();
    beginRichTurn(store);
    store.getState().completeTurn("draft-1", {
      content: [{ type: "text", text: "Done." }],
      reply: "Done.",
      userText: "Record lesson results.",
      artifactMarkdown: "# Updated diary",
      artifactRevision: 5,
      artifactHash: "hash-5",
      completeness: { items: [] },
      readyToSave: true,
      lastChangeSummary: "Filled sections.",
      memoryState: { phase: "collect_results" },
    });

    const snap = store.getState().draftsById["draft-1"];
    expect(snap.artifactMarkdown).toBe("# Updated diary");
    expect(snap.artifactRevision).toBe(5);
    expect(snap.turnInProgress).toBe(false);
    expect(snap.latestTurnComplete).toBe(true);
    expect(snap.readyToSave).toBe(true);
    expect(snap.lastChangeSummary).toBe("Filled sections.");
    expect(snap.messages.slice(-2)).toEqual([
      { role: "user", content: "Record lesson results." },
      { role: "assistant", content: "Done." },
    ]);
    const thread = store.getState().threadMessagesByDraftId["draft-1"];
    expect(thread[thread.length - 1].content).toEqual([
      { type: "text", text: "Done." },
    ]);
    expect(store.getState().turnByDraftId["draft-1"].phase).toBe("settled");
  });

  it("failTurn replaces the assistant bubble with the error and settles", () => {
    const store = createWorkflowDraftStore();
    store
      .getState()
      .upsert(snapshot({ turnInProgress: false, latestTurnComplete: true }));
    store.getState().beginTurn("draft-1", {
      userContent: "New note",
      placeholderContent: [{ type: "reasoning", text: "Starting..." }],
    });
    store.getState().failTurn("draft-1", "Something broke");

    const thread = store.getState().threadMessagesByDraftId["draft-1"];
    expect(thread[thread.length - 1].content).toEqual([
      { type: "text", text: "Something broke" },
    ]);
    const snap = store.getState().draftsById["draft-1"];
    expect(snap.turnInProgress).toBe(false);
    expect(snap.latestTurnComplete).toBe(true);
    expect(store.getState().turnByDraftId["draft-1"].phase).toBe("settled");
  });

  it("applyTurnProgress only writes while streaming", () => {
    const store = createWorkflowDraftStore();
    beginRichTurn(store);
    store.getState().markAwaitingBackend("draft-1");
    const before = store.getState().threadMessagesByDraftId["draft-1"];
    store.getState().applyTurnProgress("draft-1", [
      { type: "text", text: "should not land" },
    ]);
    expect(store.getState().threadMessagesByDraftId["draft-1"]).toBe(before);
  });
});

describe("applyDraftPatch", () => {
  it("merges PATCH metadata (incl. markdown) without touching thread or flags", () => {
    const store = createWorkflowDraftStore();
    beginRichTurn(store);
    const threadBefore = store.getState().threadMessagesByDraftId["draft-1"];

    store.getState().applyDraftPatch("draft-1", {
      artifactMarkdown: "# Teacher edited",
      artifactRevision: 9,
      artifactHash: "hash-9",
      readyToSave: true,
    });

    const snap = store.getState().draftsById["draft-1"];
    expect(snap.artifactMarkdown).toBe("# Teacher edited");
    expect(snap.artifactRevision).toBe(9);
    expect(snap.turnInProgress).toBe(true); // flags untouched
    expect(store.getState().threadMessagesByDraftId["draft-1"]).toBe(threadBefore);
  });

  it("no-ops for unknown drafts", () => {
    const store = createWorkflowDraftStore();
    store.getState().applyDraftPatch("ghost", { artifactRevision: 1 });
    expect(store.getState().draftsById["ghost"]).toBeUndefined();
  });
});

describe("mergeFinalReplyIntoThread", () => {
  it("replaces an existing text part instead of appending a second one", () => {
    const merged = mergeFinalReplyIntoThread(
      [
        { id: "u", role: "user", content: "Hi" },
        {
          id: "a",
          role: "assistant",
          content: [
            { type: "reasoning", text: "Thinking" },
            { type: "text", text: "partial" },
          ],
        },
      ],
      [{ role: "assistant", content: "Final reply." }],
    );
    const parts = merged[1].content as Array<{ type: string; text?: string }>;
    expect(parts.filter((p) => p.type === "text")).toHaveLength(1);
    expect(parts.find((p) => p.type === "text")?.text).toBe("Final reply.");
  });

  it("returns the thread unchanged when the snapshot has no assistant reply", () => {
    const thread = [
      { id: "u", role: "user" as const, content: "Hi" },
      { id: "a", role: "assistant" as const, content: [] },
    ];
    expect(mergeFinalReplyIntoThread(thread, [])).toBe(thread);
  });
});

describe("remove", () => {
  it("removes only the discarded workflow draft", () => {
    const store = createWorkflowDraftStore();
    const first = snapshot();
    const second = snapshot({ draftId: "draft-2", sessionId: "session-2" });

    store.getState().upsert(first);
    store.getState().upsert(second);
    store.getState().remove(first.draftId);

    expect(store.getState().draftsById[first.draftId]).toBeUndefined();
    expect(store.getState().draftsById[second.draftId]).toEqual(second);
  });
});
