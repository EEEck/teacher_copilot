import { afterEach, describe, expect, it, vi } from "vitest";

import { WriteVerificationBlockedError, client } from "./api";

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

  it("preserves active memory draft metadata while normalizing timeline entries", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          class_id: "chemie_9b_2026_27",
          entries: [
            {
              date: "2026-07-08",
              title: "Isomers",
              status: "planned",
              memory_draft_id: "draft-123",
            },
          ],
          months: ["2026-07"],
        }),
        { status: 200 },
      ),
    );

    const timeline = await client.getTimeline("chemie_9b_2026_27");

    expect(timeline.entries[0].memory_draft_id).toBe("draft-123");
  });

  it("rethrows WriteVerificationBlockedError for write-gate 409 responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "write_verification_blocked",
          action: "plan_save",
          artifact_fingerprint: "abc123",
          executive_state: {
            status: "needs_decision",
            open_findings: [{ finding_id: "scope-1" }],
          },
          message: "I didn't save this yet; one detail needs your call.",
        }),
        { status: 409 },
      ),
    );

    try {
      await client.planSave("chemie_9b_2026_27", "session-1", "2026-07-10", "# Plan");
      expect.unreachable("expected WriteVerificationBlockedError");
    } catch (err) {
      expect(err).toBeInstanceOf(WriteVerificationBlockedError);
      const blocked = err as WriteVerificationBlockedError;
      expect(blocked.payload.action).toBe("plan_save");
      expect(blocked.payload.artifact_fingerprint).toBe("abc123");
      expect(blocked.payload.executive_state.status).toBe("needs_decision");
      expect(blocked.message).toBe(
        "I didn't save this yet; one detail needs your call.",
      );
    }
  });
});
