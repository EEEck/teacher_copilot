import type { ChatModelRunResult } from "@assistant-ui/react";

import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";

export function initialAssistantRunContent(): ChatModelRunResult["content"] {
  return [{ type: "reasoning", text: "Starting..." }];
}

export function chatCompletionToastLabel(mode: ArtifactMode): string {
  return mode === "plan" ? "Lesson plan done" : "Draft update done";
}
