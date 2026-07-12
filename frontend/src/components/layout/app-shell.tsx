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
  const { wide } = useShellLayout();
  const contentWidth = wide ? "max-w-screen-2xl" : "max-w-7xl";

  return (
    <div className={cn("flex min-h-screen flex-col bg-background", className)}>
      <header className="shrink-0 border-b border-border bg-background">
        <div
          className={cn(
            "mx-auto flex h-14 items-center justify-between px-6",
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
            <span>Teacher copilot</span>
          </nav>
        </div>
      </header>
      <main
        className={cn(
          "mx-auto flex w-full min-h-0 flex-1 flex-col px-6 py-6",
          contentWidth,
        )}
      >
        {children}
      </main>
    </div>
  );
}
