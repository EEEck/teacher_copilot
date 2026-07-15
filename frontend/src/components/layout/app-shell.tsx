"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { useShellLayout } from "@/components/layout/shell-layout";

export function AppShell({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const { wide, flush } = useShellLayout();
  const contentWidth = flush
    ? "max-w-[min(100%,1800px)]"
    : wide
      ? "max-w-screen-2xl"
      : "max-w-7xl";

  return (
    <div
      className={cn(
        "flex flex-col bg-background",
        flush
          ? "h-dvh min-h-0 overflow-hidden"
          : "min-h-screen",
        className,
      )}
    >
      <header className="shrink-0 border-b border-border bg-background">
        <div
          className={cn(
            "mx-auto flex items-center justify-between",
            flush ? "h-12 px-3" : "h-14 px-6",
            contentWidth,
          )}
        >
          <Link href="/" className="font-semibold tracking-tight text-primary">
            KlassenPilot
          </Link>
          <nav className="flex items-center gap-4 text-xs text-muted-foreground">
            <Link href="/docs" className="hover:text-foreground">
              Docs
            </Link>
            <Link href="/beta/feedback" className="hover:text-foreground">
              Feedback
            </Link>
            <span>Teacher copilot</span>
          </nav>
        </div>
      </header>
      <main
        className={cn(
          "mx-auto flex w-full min-h-0 flex-1 flex-col",
          flush ? "px-3 py-2" : "px-6 py-6",
          contentWidth,
        )}
      >
        {children}
      </main>
    </div>
  );
}
