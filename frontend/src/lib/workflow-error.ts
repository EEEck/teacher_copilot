import { WriteVerificationBlockedError } from "@/lib/api";
import {
  errorMessageFromUnknown,
  writeVerificationErrorMessage,
} from "@/lib/write-verification-error";

export type WorkflowErrorChannel = "action_needed" | "system";

export type ClassifiedWorkflowError = {
  channel: WorkflowErrorChannel;
  message: string;
  /** Show “Respond in chat” on the action-needed card. */
  respondInChat: boolean;
};

/**
 * Split teacher-facing failures into two channels:
 * - action_needed: executive write-gate / needs a chat reply (in-chat card)
 * - system: network, bootstrap, discard, other ops (page banner)
 */
export function classifyWorkflowError(
  error: unknown,
  fallback: string,
): ClassifiedWorkflowError {
  if (error instanceof WriteVerificationBlockedError) {
    return {
      channel: "action_needed",
      message:
        writeVerificationErrorMessage(error) ??
        error.message ??
        "I didn't save this yet; one detail needs your call.",
      respondInChat: true,
    };
  }
  return {
    channel: "system",
    message: errorMessageFromUnknown(error, fallback),
    respondInChat: false,
  };
}

/** Route a classified error to the action-needed card or system banner. */
export function routeWorkflowError(
  classified: ClassifiedWorkflowError,
  handlers: {
    onActionNeeded: (payload: {
      message: string;
      respondInChat: boolean;
    }) => void;
    onSystem: (message: string) => void;
  },
): void {
  if (classified.channel === "action_needed") {
    handlers.onActionNeeded({
      message: classified.message,
      respondInChat: classified.respondInChat,
    });
    return;
  }
  handlers.onSystem(classified.message);
}
