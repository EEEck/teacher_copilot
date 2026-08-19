"use client";

import Link from "next/link";
import { Suspense } from "react";

import { AppMenuSheet } from "@/components/layout/app-menu-sheet";
import { BetaProfileGate } from "@/components/layout/beta-profile-gate";

import { useShellLayout } from "@/components/layout/shell-layout";

import { cn } from "@/lib/utils";



export function AppShell({

  children,

  className,

  betaEnabled = process.env.NEXT_PUBLIC_BETA_ENABLED === "true",

}: {

  children: React.ReactNode;

  className?: string;

  betaEnabled?: boolean;

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

          <AppMenuSheet betaEnabled={betaEnabled} />

        </div>

      </header>

      {betaEnabled && (
        <Suspense fallback={null}>
          <BetaProfileGate />
        </Suspense>
      )}

      <main

        className={cn(

          "mx-auto flex w-full min-h-0 flex-1 flex-col",

          flush ? "overflow-y-auto px-3 py-2" : "px-6 py-6",

          contentWidth,

        )}

      >

        {children}

      </main>

    </div>

  );

}

