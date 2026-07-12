import { describe, expect, it } from "vitest";

import {
  replaceLastAssistantContent,
  truncateThreadBeforeEdit,
} from "./thread-messages";

describe("replaceLastAssistantContent", () => {
  it("replaces only the latest assistant message while preserving the user turn", () => {
    const messages = [
      { id: "user-1", role: "user" as const, content: "Record the lesson." },
      {
        id: "assistant-1",
        role: "assistant" as const,
        content: [{ type: "reasoning" as const, text: "Starting..." }],
      },
    ];

    expect(
      replaceLastAssistantContent(messages, [
        { type: "tool-call", toolCallId: "call-1", toolName: "search_memory", args: {} },
      ]),
    ).toEqual([
      messages[0],
      {
        id: "assistant-1",
        role: "assistant",
        content: [
          { type: "tool-call", toolCallId: "call-1", toolName: "search_memory", args: {} },
        ],
      },
    ]);
  });
});

describe("truncateThreadBeforeEdit", () => {
  const messages = [
    { id: "persisted-0", role: "user" as const, content: "First note" },
    { id: "persisted-1", role: "assistant" as const, content: "First reply" },
    { id: "persisted-2", role: "user" as const, content: "Second note" },
    { id: "persisted-3", role: "assistant" as const, content: "Second reply" },
  ];

  it("keeps messages through the parent and drops the edited turn onward", () => {
    expect(truncateThreadBeforeEdit(messages, "persisted-1")).toEqual([
      messages[0],
      messages[1],
    ]);
  });

  it("clears the thread when editing the first user message", () => {
    expect(truncateThreadBeforeEdit(messages, null)).toEqual([]);
  });

  it("clears the thread when the parent id is unknown", () => {
    expect(truncateThreadBeforeEdit(messages, "missing")).toEqual([]);
  });
});
