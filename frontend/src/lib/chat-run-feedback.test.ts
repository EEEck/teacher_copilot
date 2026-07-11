import { describe, expect, it } from "vitest";

import {
  chatCompletionToastLabel,
  chatFailureToastLabel,
  chatRunningTaskLabel,
  initialAssistantRunContent,
  lessonContextFromMemoryState,
} from "./chat-run-feedback";

describe("chat run feedback", () => {
  it("provides immediate visible feedback before backend stream progress arrives", () => {
    expect(initialAssistantRunContent()).toEqual([
      { type: "reasoning", text: "Starting..." },
    ]);
  });

  it("labels running and finished workflow tasks with lesson context", () => {
    expect(
      chatRunningTaskLabel({
        mode: "ingest",
        lessonTitle: "Ions review",
        lessonDate: "2026-07-10",
      }),
    ).toBe("Updating memory for Ions review");
    expect(
      chatRunningTaskLabel({ mode: "plan", lessonDate: "2026-07-10" }),
    ).toBe("Planning lesson for 2026-07-10");
    expect(chatRunningTaskLabel({ mode: "plan" })).toBe("Planning lesson");
    expect(chatRunningTaskLabel({ mode: "memory_sweep" })).toBe(
      "Generating memory sweep…",
    );

    expect(
      chatCompletionToastLabel({
        mode: "ingest",
        lessonTitle: "Ions review",
        lessonDate: "2026-07-10",
      }),
    ).toBe("Finished updating memory for Ions review");
    expect(
      chatCompletionToastLabel({ mode: "plan", lessonDate: "2026-07-10" }),
    ).toBe("Finished lesson planning for 2026-07-10");
    expect(chatCompletionToastLabel("ingest")).toBe("Finished updating memory");
    expect(chatCompletionToastLabel("plan")).toBe("Finished lesson planning");
    expect(chatCompletionToastLabel("memory_sweep")).toBe("Finished memory sweep");
    expect(chatFailureToastLabel({ mode: "memory_sweep" })).toBe(
      "Memory sweep failed",
    );
  });

  it("reads lesson target fields from ingest memory state", () => {
    expect(
      lessonContextFromMemoryState({
        target: { lesson_date: "2026-07-10", lesson_title: "Ions review" },
      }),
    ).toEqual({ lessonDate: "2026-07-10", lessonTitle: "Ions review" });
    expect(lessonContextFromMemoryState(null)).toEqual({});
  });
});
