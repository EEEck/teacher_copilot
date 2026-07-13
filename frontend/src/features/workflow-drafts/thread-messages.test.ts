import { describe, expect, it } from "vitest";

import {
  isPlaceholderAssistantContent,
  lastAssistantContent,
} from "./thread-messages";

describe("assistant content helpers", () => {
  it("treats the initial Starting… reasoning bubble as a placeholder", () => {
    expect(
      isPlaceholderAssistantContent([{ type: "reasoning", text: "Starting..." }]),
    ).toBe(true);
  });

  it("keeps real reasoning / text as non-placeholder", () => {
    expect(
      isPlaceholderAssistantContent([
        { type: "reasoning", text: "Working through the request..." },
        { type: "text", text: "Here is the answer." },
      ]),
    ).toBe(false);
  });

  it("reads the last assistant content from the thread", () => {
    expect(
      lastAssistantContent([
        { id: "u1", role: "user", content: "Hi" },
        {
          id: "a1",
          role: "assistant",
          content: [{ type: "reasoning", text: "Thinking" }],
        },
      ]),
    ).toEqual([{ type: "reasoning", text: "Thinking" }]);
  });
});
