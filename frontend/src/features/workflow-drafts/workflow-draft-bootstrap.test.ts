import { describe, expect, it } from "vitest";

import { toWorkflowDraftSnapshot } from "./workflow-draft-bootstrap";

describe("toWorkflowDraftSnapshot", () => {
  it("normalizes an Update Memory bootstrap response into a backend-backed draft snapshot", () => {
    expect(
      toWorkflowDraftSnapshot("ingest", "chemie_9b_2026_27", {
        sessionId: "session-1",
        draftId: "draft-1",
        initialMessages: [{ role: "user", content: "Record results." }],
        initialMarkdown: "# Results",
        artifactRevision: 3,
        artifactHash: "hash-3",
        turnInProgress: true,
        latestTurnComplete: false,
      }),
    ).toEqual({
      mode: "ingest",
      classId: "chemie_9b_2026_27",
      sessionId: "session-1",
      draftId: "draft-1",
      messages: [{ role: "user", content: "Record results." }],
      artifactMarkdown: "# Results",
      artifactRevision: 3,
      artifactHash: "hash-3",
      turnInProgress: true,
      latestTurnComplete: false,
    });
  });

  it("does not cache legacy sessions without a durable draft id", () => {
    expect(
      toWorkflowDraftSnapshot("plan", "chemie_9b_2026_27", {
        sessionId: "legacy-session",
        initialMarkdown: "# Plan",
      }),
    ).toBeNull();
  });
});
