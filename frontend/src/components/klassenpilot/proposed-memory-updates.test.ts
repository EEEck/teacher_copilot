import { describe, expect, it } from "vitest";

import {
  splitPostSaveMemoryCandidates,
  toApplicableMemoryCandidate,
} from "./proposed-memory-updates";

describe("toApplicableMemoryCandidate", () => {
  it("maps human proposal labels to canonical apply targets", () => {
    const normalized = toApplicableMemoryCandidate({
      target: "Planning Patterns",
      section: "Avoid",
      candidate_update: "Avoid rote memorization as the main strategy.",
      evidence: "Teacher corrected the planning style.",
      source: "explicit",
      basis: "explicit",
      confidence: "high",
      requires_teacher_approval: true,
    });

    expect(normalized.canApply).toBe(true);
    expect(normalized.candidate.target).toBe("copilot_profile.md");
    expect(normalized.candidate.section).toBe("Avoid");
  });

  it("keeps inferred plan candidates as sweep signals instead of apply-now updates", () => {
    const split = splitPostSaveMemoryCandidates([
      {
        target: "copilot_profile.md",
        section: "Planning Patterns",
        candidate_update: "Use a timed 5/15/10/10/5 structure.",
        evidence: "This was used in one lesson plan.",
        source: "inferred_from_session",
        basis: "explicit",
        confidence: "high",
        requires_teacher_approval: true,
      },
      {
        target: "teacher_profile.md",
        section: "Communication",
        candidate_update: "Always keep future lesson plans in English.",
        evidence:
          "Direct teacher quote: From now on, always keep future lesson plans in English.",
        source: "teacher_explicit",
        basis: "explicit",
        confidence: "high",
        fast_lane: true,
        requires_teacher_approval: true,
      },
    ]);

    expect(split.signals).toHaveLength(1);
    expect(split.signals[0]?.candidate_update).toContain("timed");
    expect(split.immediate).toHaveLength(1);
    expect(split.immediate[0]?.candidate_update).toContain("English");
  });

  it("does not infer apply-now status from source or quote markers", () => {
    const split = splitPostSaveMemoryCandidates([
      {
        target: "teacher_profile.md",
        section: "Communication",
        candidate_update: "Always keep future lesson plans in English.",
        evidence:
          "Direct teacher quote: From now on, always keep future lesson plans in English.",
        source: "teacher_explicit",
        basis: "explicit",
        confidence: "high",
        fast_lane: false,
        requires_teacher_approval: true,
      },
    ]);

    expect(split.immediate).toHaveLength(0);
    expect(split.signals).toHaveLength(1);
  });

  it("uses backend fast_lane even for supported content targets", () => {
    const split = splitPostSaveMemoryCandidates([
      {
        target: "teaching_patterns.md",
        section: "Class Learning Profile",
        candidate_update:
          "Organic chemistry works better with molecule kits before terminology.",
        evidence:
          "Direct teacher quote: For the next block of organic chemistry, always use molecule kits before terminology.",
        source: "teacher_explicit",
        basis: "explicit",
        confidence: "high",
        fast_lane: true,
        requires_teacher_approval: true,
      },
      {
        target: "class_state.md",
        section: "Current Unit",
        candidate_update: "The class is moving into organic chemistry.",
        evidence:
          "Direct teacher quote: From now on, remember that we are starting organic chemistry.",
        source: "teacher_explicit",
        basis: "explicit",
        confidence: "high",
        fast_lane: false,
        requires_teacher_approval: true,
      },
    ]);

    expect(split.immediate).toHaveLength(1);
    expect(split.immediate[0]?.target).toBe("teaching_patterns.md");
    expect(split.signals).toHaveLength(1);
    expect(split.signals[0]?.target).toBe("class_state.md");
  });
});
