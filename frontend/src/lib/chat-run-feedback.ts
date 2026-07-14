import type { ChatModelRunResult } from "@assistant-ui/react";

import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";
import type { PendingJobMode } from "@/lib/pending-chat-turns";

export type WorkflowTaskLabelContext = {
  mode: PendingJobMode;
  lessonDate?: string;
  lessonTitle?: string;
};

export function initialAssistantRunContent(): ChatModelRunResult["content"] {
  return [{ type: "reasoning", text: "Starting..." }];
}

function lessonSubject({
  lessonDate,
  lessonTitle,
}: Pick<WorkflowTaskLabelContext, "lessonDate" | "lessonTitle">): string {
  const title = lessonTitle?.trim() ?? "";
  if (title) return title;
  const date = lessonDate?.trim() ?? "";
  return date;
}

export function chatRunningTaskLabel(ctx: WorkflowTaskLabelContext): string {
  if (ctx.mode === "memory_sweep") {
    return "Generating memory sweep…";
  }
  if (ctx.mode === "discuss") {
    return "Discussing class state";
  }
  const subject = lessonSubject(ctx);
  if (ctx.mode === "plan") {
    return subject ? `Planning lesson for ${subject}` : "Planning lesson";
  }
  return subject ? `Updating memory for ${subject}` : "Updating memory";
}

export function chatCompletionToastLabel(
  ctx: WorkflowTaskLabelContext | ArtifactMode | "memory_sweep",
): string {
  const normalized: WorkflowTaskLabelContext =
    typeof ctx === "string" ? { mode: ctx } : ctx;
  if (normalized.mode === "memory_sweep") {
    return "Finished memory sweep";
  }
  if (normalized.mode === "discuss") {
    return "Finished class discussion";
  }
  const subject = lessonSubject(normalized);
  if (normalized.mode === "plan") {
    return subject
      ? `Finished lesson planning for ${subject}`
      : "Finished lesson planning";
  }
  return subject
    ? `Finished updating memory for ${subject}`
    : "Finished updating memory";
}

export function chatFailureToastLabel(ctx: WorkflowTaskLabelContext): string {
  if (ctx.mode === "memory_sweep") {
    return "Memory sweep failed";
  }
  if (ctx.mode === "discuss") {
    return "Class discussion didn't finish — reopen it to retry";
  }
  const subject = lessonSubject(ctx);
  if (ctx.mode === "plan") {
    return subject
      ? `Lesson plan for ${subject} didn't finish — open the draft to retry`
      : "Lesson plan didn't finish — open the draft to retry";
  }
  return subject
    ? `Memory update for ${subject} didn't finish — open the draft to retry`
    : "Memory update didn't finish — open the draft to retry";
}

/** Read lesson target fields from ingest memory_state.target when present. */
export function lessonContextFromMemoryState(
  memoryState: Record<string, unknown> | null | undefined,
): { lessonDate?: string; lessonTitle?: string } {
  if (!memoryState || typeof memoryState !== "object") return {};
  const target = memoryState.target;
  if (!target || typeof target !== "object") return {};
  const record = target as Record<string, unknown>;
  const lessonDate =
    typeof record.lesson_date === "string" && record.lesson_date.trim()
      ? record.lesson_date.trim()
      : undefined;
  const lessonTitle =
    typeof record.lesson_title === "string" && record.lesson_title.trim()
      ? record.lesson_title.trim()
      : undefined;
  return { lessonDate, lessonTitle };
}
