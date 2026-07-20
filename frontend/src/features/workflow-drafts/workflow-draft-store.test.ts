import { describe, expect, it } from "vitest";

import {
  createWorkflowDraftStore,
  selectThreadMessages,
  shouldKeepLiveThread,
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

describe("shouldKeepLiveThread", () => {
  it("keeps a rich live thread over a plain same-length snapshot", () => {
    expect(
      shouldKeepLiveThread(
        [
          { id: "u", role: "user", content: "Hi" },
          {
            id: "a",
            role: "assistant",
            content: [{ type: "reasoning", text: "Thinking" }],
          },
        ],
        [
          { role: "user", content: "Hi" },
          { role: "assistant", content: "Done." },
        ],
      ),
    ).toBe(true);
  });

  it("replaces when the previous thread is empty or plain", () => {
    expect(
      shouldKeepLiveThread([], [{ role: "user", content: "Hi" }]),
    ).toBe(false);
    expect(
      shouldKeepLiveThread(
        [{ id: "u", role: "user", content: "Hi" }],
        [
          { role: "user", content: "Hi" },
          { role: "assistant", content: "Done." },
        ],
      ),
    ).toBe(false);
  });

  it("keeps any non-empty previous thread when the snapshot has no messages", () => {
    expect(
      shouldKeepLiveThread([{ id: "u", role: "user", content: "Hi" }], []),
    ).toBe(true);
  });

  it("keeps rich parts while backend turn is in progress even if snapshot grows", () => {
    expect(
      shouldKeepLiveThread(
        [
          { id: "u", role: "user", content: "Hi" },
          {
            id: "a",
            role: "assistant",
            content: [{ type: "reasoning", text: "Thinking" }],
          },
        ],
        [
          { role: "user", content: "Hi" },
          { role: "assistant", content: "Done." },
          { role: "user", content: "extra" },
        ],
        { turnInProgress: true },
      ),
    ).toBe(true);
  });
});

describe("workflow draft store", () => {
  it("returns one stable empty thread snapshot before a draft has messages", () => {
    const store = createWorkflowDraftStore();

    const first = selectThreadMessages(store.getState(), "new-draft");
    const second = selectThreadMessages(store.getState(), "new-draft");

    expect(first).toBe(second);
    expect(first).toEqual([]);
  });

  it("merges the final reply into a rich thread that never got SSE text", () => {
    const store = createWorkflowDraftStore();
    const draftId = "draft-merge";
    store.getState().upsert(
      snapshot({
        draftId,
        sessionId: "session-merge",
        messages: [
          { role: "user", content: "Hi" },
          { role: "assistant", content: "" },
        ],
        turnInProgress: true,
        latestTurnComplete: false,
      }),
    );
    store.getState().setThreadMessages(draftId, [
      { id: "u", role: "user", content: "Hi" },
      {
        id: "a",
        role: "assistant",
        content: [
          { type: "reasoning", text: "Thinking" },
          {
            type: "tool-call",
            toolName: "search",
            toolCallId: "t1",
            args: {},
            argsText: "{}",
          },
        ],
      },
    ]);

    store.getState().upsert(
      snapshot({
        draftId,
        sessionId: "session-merge",
        messages: [
          { role: "user", content: "Hi" },
          { role: "assistant", content: "Here is the draft." },
        ],
        turnInProgress: false,
        latestTurnComplete: true,
      }),
    );

    const thread = store.getState().threadMessagesByDraftId[draftId];
    const assistant = thread[1];
    expect(Array.isArray(assistant.content)).toBe(true);
    const parts = assistant.content as Array<{ type: string; text?: string }>;
    expect(parts.some((p) => p.type === "reasoning")).toBe(true);
    expect(parts.some((p) => p.type === "text" && p.text === "Here is the draft.")).toBe(
      true,
    );
    expect(store.getState().draftsById[draftId].turnInProgress).toBe(false);
  });

  it("replaces a running snapshot with the persisted completed chat turn", () => {
    const store = createWorkflowDraftStore();
    const running = snapshot();
    const completed = snapshot({
      messages: [
        ...running.messages,
        { role: "assistant", content: "The lesson diary is ready." },
      ],
      artifactMarkdown: "# Completed lesson results",
      artifactRevision: 2,
      artifactHash: "hash-2",
      turnInProgress: false,
      latestTurnComplete: true,
    });

    store.getState().upsert(running);
    store.getState().upsert(completed);

    expect(store.getState().draftsById[completed.draftId]).toEqual(completed);
    expect(store.getState().draftsById[completed.draftId]).not.toBe(running);
  });

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

  it("derives the visible assistant-ui thread from the latest backend snapshot", () => {
    const store = createWorkflowDraftStore();
    const completed = snapshot({
      messages: [
        { role: "user", content: "Record lesson results." },
        { role: "assistant", content: "The lesson diary is ready." },
      ],
      turnInProgress: false,
      latestTurnComplete: true,
    });

    store.getState().upsert(completed);

    expect(store.getState().threadMessagesByDraftId[completed.draftId]).toEqual([
      { id: "persisted-0", role: "user", content: "Record lesson results." },
      {
        id: "persisted-1",
        role: "assistant",
        content: "The lesson diary is ready.",
      },
    ]);
  });

  it("holds live assistant-ui stream parts until the backend sends a replacement snapshot", () => {
    const store = createWorkflowDraftStore();
    const running = snapshot();
    store.getState().upsert(running);

    store.getState().setThreadMessages(running.draftId, [
      { id: "persisted-0", role: "user", content: "Record lesson results." },
      {
        id: "streaming-1",
        role: "assistant",
        content: [{ type: "reasoning", text: "Reading class memory..." }],
      },
    ]);

    expect(store.getState().threadMessagesByDraftId[running.draftId]).toEqual([
      { id: "persisted-0", role: "user", content: "Record lesson results." },
      {
        id: "streaming-1",
        role: "assistant",
        content: [{ type: "reasoning", text: "Reading class memory..." }],
      },
    ]);
  });

  it("keeps rich live parts when a plain completion snapshot arrives", () => {
    const store = createWorkflowDraftStore();
    store.getState().upsert(
      snapshot({
        messages: [{ role: "user", content: "Record lesson results." }],
        turnInProgress: true,
        latestTurnComplete: false,
      }),
    );
    store.getState().setThreadMessages("draft-1", [
      { id: "persisted-0", role: "user", content: "Record lesson results." },
      {
        id: "streaming-1",
        role: "assistant",
        content: [
          { type: "reasoning", text: "Still working..." },
          { type: "text", text: "The lesson diary is ready." },
        ],
      },
    ]);

    store.getState().upsert(
      snapshot({
        messages: [
          { role: "user", content: "Record lesson results." },
          { role: "assistant", content: "The lesson diary is ready." },
        ],
        turnInProgress: false,
        latestTurnComplete: true,
        artifactRevision: 2,
        artifactHash: "hash-2",
      }),
    );

    expect(store.getState().draftsById["draft-1"].turnInProgress).toBe(false);
    expect(store.getState().threadMessagesByDraftId["draft-1"]).toEqual([
      { id: "persisted-0", role: "user", content: "Record lesson results." },
      {
        id: "streaming-1",
        role: "assistant",
        content: [
          { type: "reasoning", text: "Still working..." },
          { type: "text", text: "The lesson diary is ready." },
        ],
      },
    ]);
  });

  it("does not wipe a live thread when an empty draft snapshot arrives", () => {
    const store = createWorkflowDraftStore();
    store.getState().upsert(
      snapshot({
        messages: [{ role: "user", content: "Record lesson results." }],
      }),
    );
    store.getState().setThreadMessages("draft-1", [
      { id: "live-0", role: "user", content: "Record lesson results." },
      {
        id: "live-1",
        role: "assistant",
        content: [{ type: "reasoning", text: "Working..." }],
      },
    ]);

    store.getState().upsert(
      snapshot({
        messages: [],
        turnInProgress: false,
        latestTurnComplete: true,
        artifactRevision: 2,
        artifactHash: "hash-2",
      }),
    );

    expect(store.getState().threadMessagesByDraftId["draft-1"]).toEqual([
      { id: "live-0", role: "user", content: "Record lesson results." },
      {
        id: "live-1",
        role: "assistant",
        content: [{ type: "reasoning", text: "Working..." }],
      },
    ]);
    expect(store.getState().draftsById["draft-1"].artifactRevision).toBe(2);
  });

  it("hydrates a plain remounted thread from a longer completion snapshot", () => {
    const store = createWorkflowDraftStore();
    store.getState().upsert(
      snapshot({
        messages: [{ role: "user", content: "Record lesson results." }],
        turnInProgress: true,
        latestTurnComplete: false,
      }),
    );

    store.getState().upsert(
      snapshot({
        messages: [
          { role: "user", content: "Record lesson results." },
          { role: "assistant", content: "The lesson diary is ready." },
        ],
        turnInProgress: false,
        latestTurnComplete: true,
        artifactRevision: 2,
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
});
