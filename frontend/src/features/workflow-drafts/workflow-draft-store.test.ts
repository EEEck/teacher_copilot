import { describe, expect, it } from "vitest";

import {
  createWorkflowDraftStore,
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

describe("workflow draft store", () => {
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

  it("replaces visible thread messages when a later backend snapshot arrives", () => {
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
        content: [{ type: "reasoning", text: "Still working..." }],
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

    // External-store runtime reads this map; no remount key is required.
    expect(store.getState().threadMessagesByDraftId["draft-1"]).toEqual([
      { id: "persisted-0", role: "user", content: "Record lesson results." },
      {
        id: "persisted-1",
        role: "assistant",
        content: "The lesson diary is ready.",
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
});
