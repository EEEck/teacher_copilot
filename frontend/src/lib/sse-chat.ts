import type { ChatModelRunResult } from "@assistant-ui/react";

import type { CompletenessChecklist } from "@/lib/api";

/** Map SSE stream parts to assistant-ui run content (tool-call requires `args`). */
export function streamPartsToRunContent(
  parts: StreamPart[],
): ChatModelRunResult["content"] {
  return parts.map((part) => {
    if (part.type !== "tool-call") return part;
    let args: Record<string, unknown> = {};
    if (part.argsText.trim()) {
      try {
        const parsed = JSON.parse(part.argsText) as unknown;
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          args = parsed as Record<string, unknown>;
        }
      } catch {
        args = { raw: part.argsText };
      }
    }
    return {
      type: "tool-call" as const,
      toolName: part.toolName,
      toolCallId: part.toolCallId,
      args,
      argsText: part.argsText,
      result: part.result,
      status: part.status,
    };
  }) as ChatModelRunResult["content"];
}

export type SseEvent =
  | { type: "reasoning_delta"; text: string }
  | { type: "tool_call"; name: string; args?: string; call_id?: string | null }
  | { type: "tool_result"; name?: string; output?: string; call_id?: string | null }
  | {
      type: "final";
      reply: string;
      artifact_markdown: string;
      ready: boolean;
      completeness?: CompletenessChecklist | null;
    }
  | { type: "error"; message: string; code?: string | null };

export type StreamPart =
  | { type: "reasoning"; text: string }
  | {
      type: "tool-call";
      toolName: string;
      toolCallId: string;
      argsText: string;
      result?: unknown;
      status?: { type: "running" } | { type: "complete" };
    }
  | { type: "text"; text: string };

export type StreamChatFinal = {
  reply: string;
  artifactMarkdown: string;
  readyToSave?: boolean;
  completeness?: CompletenessChecklist | null;
};

export function parseSseChunk(buffer: string): { events: SseEvent[]; rest: string } {
  const events: SseEvent[] = [];
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  for (const block of parts) {
    for (const line of block.split("\n")) {
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      try {
        events.push(JSON.parse(payload) as SseEvent);
      } catch {
        /* skip malformed */
      }
    }
  }
  return { events, rest };
}

export class StreamPartsAccumulator {
  private reasoningText = "";
  private readonly tools = new Map<
    string,
    {
      type: "tool-call";
      toolName: string;
      toolCallId: string;
      argsText: string;
      result?: unknown;
      status?: { type: "running" } | { type: "complete" };
    }
  >();

  apply(event: SseEvent): void {
    if (event.type === "reasoning_delta") {
      this.reasoningText += event.text;
      return;
    }
    if (event.type === "tool_call") {
      const id = event.call_id ?? event.name;
      this.tools.set(id, {
        type: "tool-call",
        toolName: event.name,
        toolCallId: id,
        argsText: event.args ?? "",
        status: { type: "running" },
      });
      return;
    }
    if (event.type === "tool_result") {
      const id = event.call_id ?? event.name ?? "tool";
      const existing = this.tools.get(id);
      if (existing) {
        existing.result = event.output;
        existing.status = { type: "complete" };
      } else {
        this.tools.set(id, {
          type: "tool-call",
          toolName: event.name ?? "tool",
          toolCallId: id,
          argsText: "",
          result: event.output,
          status: { type: "complete" },
        });
      }
    }
  }

  parts(includeText?: string): StreamPart[] {
    const content: StreamPart[] = [];
    if (this.reasoningText.trim()) {
      content.push({ type: "reasoning", text: this.reasoningText });
    }
    content.push(...this.tools.values());
    if (includeText) {
      content.push({ type: "text", text: includeText });
    }
    return content;
  }
}

export async function* readSseJsonStream(
  response: Response,
): AsyncGenerator<SseEvent> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseChunk(buffer);
    buffer = parsed.rest;
    for (const event of parsed.events) {
      yield event;
    }
  }
  if (buffer.trim()) {
    const parsed = parseSseChunk(buffer + "\n\n");
    for (const event of parsed.events) {
      yield event;
    }
  }
}

export async function consumeArtifactChatStream(
  response: Response,
): Promise<{ parts: StreamPart[]; final: StreamChatFinal | null; error: string | null }> {
  const acc = new StreamPartsAccumulator();
  let final: StreamChatFinal | null = null;
  let error: string | null = null;

  for await (const event of readSseJsonStream(response)) {
    if (event.type === "error") {
      error = event.message;
      break;
    }
    if (event.type === "final") {
      final = {
        reply: event.reply,
        artifactMarkdown: event.artifact_markdown,
        readyToSave: event.ready,
        completeness: event.completeness ?? null,
      };
      break;
    }
    acc.apply(event);
  }

  const text = final?.reply ?? (error ? "" : undefined);
  return {
    parts: acc.parts(text),
    final,
    error,
  };
}
