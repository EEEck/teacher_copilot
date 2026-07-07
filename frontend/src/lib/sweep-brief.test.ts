import { describe, expect, it } from "vitest";

import type { MemorySweepCandidate } from "@/lib/api";
import { sweepBriefRows, sweepTargetLabel } from "./sweep-brief";

function candidate(
  overrides: Partial<MemorySweepCandidate>,
): MemorySweepCandidate {
  return {
    card_id: "card_x",
    source_group_id: "g",
    candidate_id: "cand_x",
    candidate_ids: ["cand_x"],
    review_queue: "Teacher/Copilot Preferences",
    channel: "teacher_behavior",
    target: "teacher_profile.md",
    section: "Communication",
    content: "Some durable claim.",
    evidence_summary: "",
    evidence_refs: [],
    confidence: "medium",
    basis: "inferred",
    status: "proposed",
    relationship: "",
    group_label: "",
    public_rationale: "",
    operation: "add",
    replaces_content: "",
    status_recommendation: "promote",
    why_now: "",
    current_memory_excerpt: "",
    signal_count: 1,
    can_apply: true,
    review_only_reason: "",
    warnings: [],
    ...overrides,
  } as MemorySweepCandidate;
}

describe("sweepBriefRows", () => {
  it("pins explicit asks first, then new, changed, removed", () => {
    const rows = sweepBriefRows([
      candidate({ card_id: "c_removed", operation: "already_covered", can_apply: false }),
      candidate({ card_id: "c_changed", operation: "adjust" }),
      candidate({ card_id: "c_new", operation: "add" }),
      candidate({ card_id: "c_explicit", operation: "add", group_label: "explicit_ask" }),
    ]);
    expect(rows.map((r) => r.section)).toEqual([
      "explicit",
      "new",
      "changed",
      "removed",
    ]);
    expect(rows[0].key).toBe("c_explicit");
  });

  it("routes needs_decision and reject_low_signal into the removed bucket", () => {
    const rows = sweepBriefRows([
      candidate({ card_id: "a", operation: "needs_decision", can_apply: false }),
      candidate({ card_id: "b", operation: "reject_low_signal", can_apply: false }),
    ]);
    expect(rows.every((r) => r.section === "removed")).toBe(true);
  });

  it("summarizes content on one line and keeps occasion counts", () => {
    const rows = sweepBriefRows([
      candidate({
        content: "Line one\n  with   wrapping  " + "x".repeat(200),
        signal_count: 4,
        occasion_count: 3,
      }),
    ]);
    expect(rows[0].summary).not.toContain("\n");
    expect(rows[0].summary.length).toBeLessThanOrEqual(130);
    expect(rows[0].occasionCount).toBe(3);
  });
});

describe("sweepTargetLabel", () => {
  it("maps memory targets to teacher language", () => {
    expect(sweepTargetLabel("teacher_profile.md")).toBe("Teacher profile");
    expect(sweepTargetLabel("copilot_profile.md")).toBe("Class copilot profile");
    expect(sweepTargetLabel("planning_brief.md")).toBe("Planning brief");
    expect(sweepTargetLabel("students/S-046.md")).toBe("Student S-046");
    expect(sweepTargetLabel("wiki/subjects/chemie.md")).toBe(
      "Subject guide (chemie)",
    );
    expect(sweepTargetLabel("something_else.md")).toBe("something_else.md");
  });
});
