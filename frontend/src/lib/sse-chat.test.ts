import { assert, describe, expect, it } from "vitest";

import {
  parseSseChunk,
  streamPartsToRunContent,
  StreamPartsAccumulator,
  type SseEvent,
} from "./sse-chat";

describe("parseSseChunk", () => {
  it("parses complete SSE blocks and keeps a trailing partial buffer", () => {
    const buffer =
      'data: {"type":"reasoning_delta","text":"Hi"}\n\n' +
      'data: {"type":"final","reply":"ok","artifact_markdown":"# x","ready":true}\n\n' +
      'data: {"type":"reasoning_delta","text":"par';
    const { events, rest } = parseSseChunk(buffer);
    expect(events).toHaveLength(2);
    expect(events[0]).toMatchObject({ type: "reasoning_delta", text: "Hi" });
    expect(events[1]).toMatchObject({ type: "final", reply: "ok" });
    expect(rest).toContain("par");
  });
});

describe("StreamPartsAccumulator", () => {
  it("accumulates reasoning, tool call, and tool result", () => {
    const acc = new StreamPartsAccumulator();
    const events: SseEvent[] = [
      { type: "reasoning_delta", text: "Thinking…" },
      { type: "tool_call", name: "search_wiki", args: '{"q":"redox"}', call_id: "c1" },
      { type: "tool_result", name: "search_wiki", output: "hits", call_id: "c1" },
    ];
    for (const e of events) acc.apply(e);
    const parts = acc.parts("Done.");
    expect(parts[0]).toEqual({ type: "reasoning", text: "Thinking…" });
    const tool = parts.find((p) => p.type === "tool-call");
    expect(tool).toMatchObject({
      toolName: "search_wiki",
      toolCallId: "c1",
      argsText: '{"q":"redox"}',
      result: "hits",
      status: { type: "complete" },
    });
    expect(parts.at(-1)).toEqual({ type: "text", text: "Done." });
  });

  it("does not double-append a full reasoning snapshot after deltas", () => {
    const acc = new StreamPartsAccumulator();
    acc.apply({ type: "reasoning_delta", text: "Hello " });
    acc.apply({ type: "reasoning_delta", text: "world" });
    acc.apply({ type: "reasoning_delta", text: "Hello world" });
    expect(acc.parts()).toEqual([{ type: "reasoning", text: "Hello world" }]);
  });
});

describe("streamPartsToRunContent", () => {
  it("parses tool args JSON for assistant-ui", () => {
    const content = streamPartsToRunContent([
      {
        type: "tool-call",
        toolName: "search_wiki",
        toolCallId: "c1",
        argsText: '{"q":"acids"}',
      },
    ]);
    assert(content);
    expect(content).toHaveLength(1);
    const part = content[0];
    assert(part);
    expect(part.type).toBe("tool-call");
    if (part.type === "tool-call") {
      expect(part.args).toEqual({ q: "acids" });
    }
  });

  it("falls back to raw args text when JSON is invalid", () => {
    const content = streamPartsToRunContent([
      {
        type: "tool-call",
        toolName: "search_wiki",
        toolCallId: "c1",
        argsText: "not-json",
      },
    ]);
    assert(content);
    expect(content).toHaveLength(1);
    const part = content[0];
    assert(part);
    if (part.type === "tool-call") {
      expect(part.args).toEqual({ raw: "not-json" });
    }
  });

  it("renders stripped production tool events without raw args or result data", () => {
    const acc = new StreamPartsAccumulator();
    acc.apply({
      type: "tool_call",
      name: "search_memory",
      args: "",
      call_id: "c1",
    });
    acc.apply({
      type: "tool_result",
      name: "search_memory",
      output: "",
      call_id: "c1",
    });

    const content = streamPartsToRunContent(acc.parts());

    assert(content);
    expect(content).toHaveLength(1);
    const part = content[0];
    assert(part);
    expect(part.type).toBe("tool-call");
    if (part.type === "tool-call") {
      expect(part.toolName).toBe("search_memory");
      expect(part.args).toEqual({});
      expect(part.argsText).toBe("");
      expect(part.result).toBe("");
    }
  });
});
