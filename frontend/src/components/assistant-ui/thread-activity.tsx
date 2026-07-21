import React, { type ReactNode } from "react";

/**
 * Runtime-owned content that follows the chat history without becoming a
 * synthetic assistant message. The caller owns its state and actions.
 */
export function ThreadActivity({ children }: { children: ReactNode }) {
  return (
    <div data-slot="thread-activity" className="pb-2">
      {children}
    </div>
  );
}
