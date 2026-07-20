"use client";

import React, { type ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Matches assistant-ui ToolGroup muted panel so review feels part of the chat column. */
export function ReviewChrome({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "w-full rounded-lg border border-muted-foreground/30 bg-muted/30",
        className,
      )}
    >
      {children}
    </div>
  );
}
