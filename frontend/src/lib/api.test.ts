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
});
