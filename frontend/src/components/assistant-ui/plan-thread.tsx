"use client";

import { OpeningMessageSeeder } from "@/components/assistant-ui/opening-message-seeder";
import { Thread } from "@/components/assistant-ui/thread";

export function PlanThread({ openingMessage }: { openingMessage: string }) {
  return (
    <>
      <OpeningMessageSeeder message={openingMessage} />
      <Thread
        showSuggestions={false}
        welcome={{
          title: "Plan your next lesson",
          subtitle:
            "Chat about goals and timing. Use + to attach a worksheet or draft plan (.md or .txt). Edit the plan on the right, then save when ready.",
        }}
        welcomeExtra={
          <ul className="aui-thread-welcome-message-inner mt-4 list-disc space-y-1 pl-5 text-sm text-muted-foreground delay-100 duration-200">
            <li>I load class memory automatically — last lesson, open loops, misconceptions.</li>
            <li>The plan draft updates as we talk; you can edit it anytime.</li>
            <li>Click Ready to save plan when you want to attach it to a lesson date.</li>
          </ul>
        }
      />
    </>
  );
}
