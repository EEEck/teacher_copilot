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
    // Fill leftover viewport height via the AppShell flex chain (NOT a fixed
    // max-h band). Keep stable `min-h-0` so react-resizable-panels does not
    // blink. Shared by memory + plan.
    <ResizablePanelGroup
      orientation="horizontal"
      className="min-h-[28rem] flex-1 overflow-hidden rounded-lg border"
    >
      <ResizablePanel defaultSize={58} minSize={40} className="h-full min-h-0 overflow-hidden">
        <div className="flex h-full min-h-0 flex-col gap-2 overflow-hidden p-2 md:p-3">
          <Card className="min-h-0 flex-1 basis-0 overflow-hidden py-0">
            <CardContent className="flex h-full min-h-0 flex-col p-0">
              {reviewDiff ? (
                <div className="h-[70%] shrink-0 overflow-y-auto border-b border-border p-3">
                  {reviewDiff}
                </div>
              ) : null}
              <div
                className={
                  inReview
                    ? "flex min-h-0 flex-1 basis-0 flex-col overflow-hidden"
                    : "flex h-full min-h-0 flex-1 basis-0 flex-col overflow-hidden"
                }
              >
                {thread}
              </div>
              {reviewFileList ? (
                <div className="max-h-[34%] shrink-0 overflow-y-auto border-t border-border p-3">
                  {reviewFileList}
                </div>
              ) : null}
            </CardContent>
          </Card>
          {footer ? <div className="shrink-0">{footer}</div> : null}
        </div>
      </ResizablePanel>
      <ResizableHandle withHandle />
      <ResizablePanel defaultSize={42} minSize={30} className="h-full min-h-0 overflow-hidden">
        <div className="flex h-full min-h-0 w-full min-w-0 overflow-hidden p-2 md:p-3">
          <div className="flex h-full min-h-0 w-full min-w-0 flex-1 basis-0 overflow-hidden">
            {draftPanel}
          </div>
        </div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
