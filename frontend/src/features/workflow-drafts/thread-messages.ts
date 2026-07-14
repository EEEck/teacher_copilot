import type { ThreadMessageLike } from "@assistant-ui/react";

export function replaceLastAssistantContent(
  messages: readonly ThreadMessageLike[],
  content: ThreadMessageLike["content"],
): ThreadMessageLike[] {
  const index = messages.findLastIndex((message) => message.role === "assistant");
  if (index < 0) return [...messages];
  return messages.map((message, messageIndex) =>
    messageIndex === index ? { ...message, content } : message,
  );
}

/** True when the assistant bubble is still the initial placeholder (no real stream yet). */
export function isPlaceholderAssistantContent(
  content: ThreadMessageLike["content"],
): boolean {
  if (content == null) return true;
  if (typeof content === "string") return content.trim().length === 0;
  if (!Array.isArray(content) || content.length === 0) return true;
  return !content.some((part) => {
    if (part.type === "text") return Boolean(part.text?.trim());
    if (part.type === "reasoning") {
      const text = part.text?.trim() ?? "";
      return text.length > 0 && text !== "Starting...";
    }
    if (part.type === "tool-call") return true;
    return false;
  });
}

export function lastAssistantContent(
  messages: readonly ThreadMessageLike[],
): ThreadMessageLike["content"] | undefined {
  const index = messages.findLastIndex((message) => message.role === "assistant");
  if (index < 0) return undefined;
  return messages[index]?.content;
}

/**
 * assistant-ui ExternalStore onEdit passes parentId of the message before the
 * edited turn. Keep that prefix and drop the edited message plus everything after.
 */
export function truncateThreadBeforeEdit(
  messages: readonly ThreadMessageLike[],
  parentId: string | null,
): ThreadMessageLike[] {
  if (parentId == null) return [];
  const parentIndex = messages.findIndex((message) => message.id === parentId);
  if (parentIndex < 0) return [];
  return messages.slice(0, parentIndex + 1);
}

export function newThreadMessageId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
