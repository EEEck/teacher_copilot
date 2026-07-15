import { describe, expect, it } from "vitest";

import { fetchedDraftToSnapshot } from "./workflow-draft-transport";

describe("fetchedDraftToSnapshot", () => {
  it("normalizes a completed planning draft from the existing API client", () => {
    expect(
      fetchedDraftToSnapshot("plan", "chemie_9b_2026_27", "session-1", {
        draft_id: "draft-1",
        artifact_revision: 2,
        artifact_hash: "hash-2",
        turn_in_progress: false,
        latest_turn_complete: true,
        messages: [
          { role: "user", content: "Plan the next lesson." },
          { role: "assistant", content: "The plan is ready." },
        ],
        plan_markdown: "# Lesson plan",
      }),
    ).toEqual({
      mode: "plan",
      classId: "chemie_9b_2026_27",
      sessionId: "session-1",
      draftId: "draft-1",
      messages: [
        { role: "user", content: "Plan the next lesson." },
        { role: "assistant", content: "The plan is ready." },
      ],
      artifactMarkdown: "# Lesson plan",
      artifactRevision: 2,
      artifactHash: "hash-2",
      turnInProgress: false,
      latestTurnComplete: true,
      completeness: null,
      memoryState: null,
    });
  });

  it("normalizes a discuss draft with empty artifact markdown", () => {
    expect(
      fetchedDraftToSnapshot("discuss", "chemie_9b_2026_27", "session-d", {
        draft_id: "draft-d",
        artifact_revision: 1,
        artifact_hash: "hash-d",
        turn_in_progress: false,
        latest_turn_complete: true,
        messages: [{ role: "user", content: "What should I watch?" }],
      }),
    ).toEqual({
      mode: "discuss",
      classId: "chemie_9b_2026_27",
      sessionId: "session-d",
      draftId: "draft-d",
      messages: [{ role: "user", content: "What should I watch?" }],
      artifactMarkdown: "",
      artifactRevision: 1,
      artifactHash: "hash-d",
      turnInProgress: false,
      latestTurnComplete: true,
      completeness: null,
      memoryState: null,
    });
  });
});
