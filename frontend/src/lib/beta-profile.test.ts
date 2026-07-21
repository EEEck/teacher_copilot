import { describe, expect, it } from "vitest";

import {
  betaProfileGateExemptPath,
  betaProfileInitial,
  betaProfileRedirectPath,
  formatBetaRoleLine,
  hasBetaHeaderIdentity,
  resolveBetaReturnPath,
} from "@/lib/beta-profile";
import type { BetaIdentity } from "@/lib/api";

describe("betaProfileInitial", () => {
  it("uses the first letter uppercased", () => {
    expect(betaProfileInitial("anna")).toBe("A");
  });

  it("falls back when empty", () => {
    expect(betaProfileInitial("")).toBe("?");
  });
});

describe("beta profile routing helpers", () => {
  it("exempts login and profile paths from the gate", () => {
    expect(betaProfileGateExemptPath("/beta/login")).toBe(true);
    expect(betaProfileGateExemptPath("/beta/profile")).toBe(true);
    expect(betaProfileGateExemptPath("/")).toBe(false);
  });

  it("builds a profile redirect with next", () => {
    expect(betaProfileRedirectPath("/", "")).toBe("/beta/profile?next=%2F");
  });

  it("sanitizes unsafe return paths", () => {
    expect(resolveBetaReturnPath("//evil")).toBe("/");
    expect(resolveBetaReturnPath("/classes/demo")).toBe("/classes/demo");
  });
});

describe("hasBetaHeaderIdentity", () => {
  it("requires a completed profile with a display name", () => {
    const identity = {
      tester_id: "t1",
      workspace_id: "w1",
      role: "tester",
      display_name: "Anna",
      profile_complete: true,
      member_since: "2026-01-01T00:00:00Z",
      stats: null,
    } satisfies BetaIdentity;
    expect(hasBetaHeaderIdentity(identity)).toBe(true);
    expect(hasBetaHeaderIdentity({ ...identity, profile_complete: false })).toBe(false);
  });
});

describe("formatBetaRoleLine", () => {
  it("formats tester role with member since", () => {
    expect(
      formatBetaRoleLine({ role: "tester", member_since: "2026-01-01T00:00:00Z" }),
    ).toMatch(/^Beta tester · joined /);
  });

  it("falls back to raw role without member since", () => {
    expect(formatBetaRoleLine({ role: "admin", member_since: null })).toBe("admin");
  });
});
