"use client";

import React, { type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Chat-column panel for wiki review.
 * `default` blends with tool groups; `commit` is the unmissable memory save gate.
 */
export function ReviewChrome({
  children,
  className,
  variant = "default",
}: {
  children: ReactNode;
  className?: string;
  variant?: "default" | "commit";
}) {
  return (
    <div
      className={cn(
        "w-full rounded-lg shadow-sm",
        variant === "commit"
          ? "border-2 border-primary bg-card"
          : "border border-muted-foreground/30 bg-muted/30",
        className,
      )}
    >
      {children}
    </div>
  );
}
