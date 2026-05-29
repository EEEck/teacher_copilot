"use client";

import type { ReactNode } from "react";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/assistant-ui/resizable";
import { Card, CardContent } from "@/components/ui/card";

export function ArtifactSessionWorkspace({
  thread,
  draftPanel,
  footer,
}: {
  thread: ReactNode;
  draftPanel: ReactNode;
  footer?: ReactNode;
}) {
  return (
    // Fixed `vh` height (NOT dvh): the thread scrolls *inside* the panel instead
    // of growing the page. dvh fluctuates with scrollbars/toolbars and, combined
    // with react-resizable-panels' ResizeObserver, caused a measure→resize→
    // measure feedback loop (the "blinking"). A stable vh height breaks that.
    // Shared by memory + plan, so this fixes both.
    <ResizablePanelGroup
      orientation="horizontal"
      className="h-[70vh] min-h-[32rem] rounded-lg border"
    >
      <ResizablePanel defaultSize={58} minSize={40}>
        <div className="flex h-full min-h-0 flex-col gap-3 p-4">
          <Card className="min-h-0 flex-1 overflow-hidden">
            <CardContent className="flex h-full min-h-0 flex-col p-0">
              {thread}
            </CardContent>
          </Card>
          {footer ? <div className="shrink-0">{footer}</div> : null}
        </div>
      </ResizablePanel>
      <ResizableHandle withHandle />
      <ResizablePanel defaultSize={42} minSize={30}>
        <div className="h-full min-h-0 p-4">{draftPanel}</div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
