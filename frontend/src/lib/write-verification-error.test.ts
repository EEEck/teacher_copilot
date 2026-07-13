import { describe, expect, it } from "vitest";

import { WriteVerificationBlockedError } from "@/lib/api";
import {
  errorMessageFromUnknown,
  writeVerificationErrorMessage,
} from "@/lib/write-verification-error";
import { dedupeMemoryCandidates } from "@/lib/memory-candidates";

describe("writeVerificationErrorMessage", () => {
  it("formats blocking findings for the page alert", () => {
    const err = new WriteVerificationBlockedError({
      code: "write_verification_blocked",
      action: "plan_save",
      artifact_fingerprint: "fp",
      executive_state: {
        open_findings: [
          {
            summary: "S-999 is not in the roster.",
            question: "Which student?",
            severity: "blocking",
          },
        ],
      },
      message: "I didn't save this yet; one detail needs your call.",
    });

    expect(writeVerificationErrorMessage(err)).toBe(
      [
        "I didn't save this yet; one detail needs your call.",
        "• S-999 is not in the roster. — Which student?",
      ].join("\n"),
    );
    expect(errorMessageFromUnknown(err, "Save failed")).toContain("S-999");
  });

  it("falls back for ordinary errors", () => {
    expect(writeVerificationErrorMessage(new Error("nope"))).toBeNull();
    expect(errorMessageFromUnknown(new Error("nope"), "Save failed")).toBe("nope");
  });
});

describe("dedupeMemoryCandidates", () => {
  it("keeps the first candidate per target/section/text", () => {
    expect(
      dedupeMemoryCandidates([
        {
          target: "teaching_patterns.md",
          section: "Pace",
          candidate_update: "Slow down",
        },
        {
          target: "teaching_patterns.md",
          section: "Pace",
          candidate_update: "slow down",
        },
      ]),
    ).toHaveLength(1);
  });
});
