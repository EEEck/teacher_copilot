"use client";

import { useAui } from "@assistant-ui/react";
import { useEffect, useRef } from "react";

/** Appends the session opening assistant message once the thread is empty. */
export function OpeningMessageSeeder({ message }: { message: string }) {
  const aui = useAui();
  const seeded = useRef(false);

  useEffect(() => {
    if (seeded.current || !message.trim()) return;
    seeded.current = true;
    void aui.thread().append({
      role: "assistant",
      content: [{ type: "text", text: message }],
    });
  }, [aui, message]);

  return null;
}
