"use client";

import Link from "next/link";
import { MenuIcon } from "lucide-react";

import { useShellLayout } from "@/components/layout/shell-layout";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

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
        flush ? "h-dvh min-h-0 overflow-hidden" : "min-h-screen",
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
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Open menu"
              >
                <MenuIcon className="size-5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-44">
              <DropdownMenuLabel>Menu</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link href="/docs">Docs</Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href="/settings">Settings</Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
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
