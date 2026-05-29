"use client";

import { Thread } from "@/components/assistant-ui/thread";

/**
 * Static welcome that mirrors the (working) memory thread: nothing is injected
 * into the runtime. We previously seeded a dynamic opening message via an
 * imperative `aui.thread().append()` which caused a re-render loop ("blinking"),
 * and showing it in the welcome made it vanish on the first send ("history
 * disappeared"). A plain static welcome avoids both and matches memory exactly.
 */
export function PlanThread() {
  return (
    <Thread
      showSuggestions={false}
      welcome={{
        title: "Plan your next lesson",
        subtitle:
          "Chat about goals and timing. I load class memory automatically. Use + to attach a worksheet or draft plan (.md or .txt).",
      }}
      welcomeExtra={
        <ul className="aui-thread-welcome-message-inner mt-4 list-disc space-y-1 pl-5 text-sm text-muted-foreground delay-100 duration-200">
          <li>I use last lesson, open loops, and misconceptions automatically.</li>
          <li>The plan draft on the right updates as we talk; you can edit it anytime.</li>
          <li>Click “Ready to save plan” when you want to attach it to a lesson date.</li>
        </ul>
      }
    />
  );
}
