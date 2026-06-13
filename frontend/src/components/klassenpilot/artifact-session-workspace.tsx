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
  reviewDiff,
  reviewFileList,
}: {
  thread: ReactNode;
  draftPanel: ReactNode;
  footer?: ReactNode;
  /** Shown above the thread while reviewing proposed file writes (Cursor-style diff). */
  reviewDiff?: ReactNode;
  /** Compact file list below the thread during review. */
  reviewFileList?: ReactNode;
}) {
  const inReview = Boolean(reviewDiff || reviewFileList);
  return (
    // Fixed `vh` height (NOT dvh): the thread scrolls *inside* the panel instead
    // of growing the page. dvh fluctuates with scrollbars/toolbars and, combined
    // with react-resizable-panels' ResizeObserver, caused a measure→resize→
    // measure feedback loop (the "blinking"). A stable vh height breaks that.
    // Shared by memory + plan, so this fixes both.
    <ResizablePanelGroup
      orientation="horizontal"
      className="h-[70vh] min-h-[32rem] overflow-hidden rounded-lg border"
    >
      <ResizablePanel defaultSize={58} minSize={40} className="min-h-0 overflow-hidden">
        <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden p-4">
          <Card className="min-h-0 flex-1 overflow-hidden">
            <CardContent className="flex h-full min-h-0 flex-col p-0">
              {reviewDiff ? (
                <div className="max-h-[42%] shrink-0 overflow-hidden border-b border-border p-3">
                  {reviewDiff}
                </div>
              ) : null}
              <div
                className={
                  inReview
                    ? "min-h-0 flex-1 overflow-hidden"
                    : "flex h-full min-h-0 flex-col overflow-hidden"
                }
              >
                {thread}
              </div>
              {reviewFileList ? (
                <div className="shrink-0 border-t border-border p-3">{reviewFileList}</div>
              ) : null}
            </CardContent>
          </Card>
          {footer ? <div className="shrink-0">{footer}</div> : null}
        </div>
      </ResizablePanel>
      <ResizableHandle withHandle />
      <ResizablePanel defaultSize={42} minSize={30} className="min-h-0 overflow-hidden">
        <div className="flex h-full min-h-0 overflow-hidden p-4">{draftPanel}</div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
