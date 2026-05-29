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
    <ResizablePanelGroup orientation="horizontal" className="min-h-[560px] rounded-lg border">
      <ResizablePanel defaultSize={58} minSize={40}>
        <div className="flex h-full flex-col gap-3 p-4">
          <Card className="min-h-0 flex-1 overflow-hidden">
            <CardContent className="flex h-full min-h-[480px] flex-col p-0">
              {thread}
            </CardContent>
          </Card>
          {footer}
        </div>
      </ResizablePanel>
      <ResizableHandle withHandle />
      <ResizablePanel defaultSize={42} minSize={30}>
        <div className="h-full p-4">{draftPanel}</div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
