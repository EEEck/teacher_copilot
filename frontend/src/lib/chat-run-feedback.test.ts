import { describe, expect, it } from "vitest";

import {
  chatCompletionToastLabel,
  initialAssistantRunContent,
} from "./chat-run-feedback";

describe("chat run feedback", () => {
  it("provides immediate visible feedback before backend stream progress arrives", () => {
    expect(initialAssistantRunContent()).toEqual([
      { type: "reasoning", text: "Starting..." },
    ]);
  });

  it("labels workflow completion toasts by mode", () => {
    expect(chatCompletionToastLabel("plan")).toBe("Lesson plan done");
    expect(chatCompletionToastLabel("ingest")).toBe("Draft update done");
  });
});
