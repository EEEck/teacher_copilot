import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "./api";

describe("client beta auth transport", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends browser credentials on beta login and normal API calls", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            tester_id: "t_anna",
            workspace_id: "w_anna_chem9b",
            role: "tester",
          }),
          { status: 200 },
        ),
      );

    await client.betaLogin("anna-invite");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/beta/login"),
      expect.objectContaining({ credentials: "include" }),
    );

    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ classes: [] }), { status: 200 }),
    );

    await client.getClasses();

    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining("/api/classes"),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("sends browser credentials for class brief and discussion calls", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            class_id: "chemie_9b_2026_27",
            summary: "Brief",
            recommended_action: { label: "Create lesson plan", href: "", rationale: "" },
            reasons: [],
            watch_items: [],
            source_paths: [],
            generated_at: "2026-07-03T00:00:00Z",
            cached: false,
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            session_id: "discussion-1",
            class_id: "chemie_9b_2026_27",
            messages: [],
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            reply: "Use the planning brief.",
            discussion_state: {},
            evidence_briefs: [],
            memory_candidates: [],
            source_paths: [],
            suggested_actions: [],
          }),
          { status: 200 },
        ),
      );

    await client.getClassBrief("chemie_9b_2026_27");
    await client.startClassDiscussion("chemie_9b_2026_27");
    await client.classDiscussionChat("chemie_9b_2026_27", "discussion-1", "What next?");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/api/classes/chemie_9b_2026_27/brief"),
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/api/classes/chemie_9b_2026_27/discussion/sessions"),
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      expect.stringContaining("/api/classes/chemie_9b_2026_27/discussion/sessions/discussion-1/chat"),
      expect.objectContaining({ credentials: "include" }),
    );
  });
});
