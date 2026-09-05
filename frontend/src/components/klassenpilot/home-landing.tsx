"use client";

import Link from "next/link";
import {
  ArrowRight,
  GraduationCap,
  LayoutGrid,
  Library,
  MessageCircle,
} from "lucide-react";

import { AgentMark } from "@/components/klassenpilot/agent-mark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

/** Seeded beta playground class — primary Explore target. */
export const MOCK_CLASS_HREF = "/classes/chemie_9b_2026_27";

/** Teacher-facing actions — one chip row */
const CAPABILITIES = [
  {
    label: "Plan",
    Icon: LayoutGrid,
    title: "Draft the next lesson from class memory",
  },
  {
    label: "Organize",
    Icon: Library,
    title: "Keep class information structured in the wiki",
  },
  {
    label: "Discuss",
    Icon: MessageCircle,
    title: "Chat with the agent about wiki and class state",
  },
  {
    label: "Coach",
    Icon: GraduationCap,
    title: "Teach the agent what to keep via Memory Sweep",
  },
] as const;

const chipClassName =
  "inline-flex w-full items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border border-border bg-card px-2 py-1.5 text-sm text-foreground";

/**
 * Production home marketing card (MagicPath Home v6 → locked AgentMark).
 * Compose with a quiet class list below on `/`.
 */
export function HomeLanding({ onCreateClass }: { onCreateClass?: () => void }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card p-8 shadow-sm sm:p-10 lg:p-12">
      <header className="relative">
        <div className="min-w-0 md:pr-[9.75rem]">
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            <span className="size-1.5 shrink-0 rounded-full bg-primary" aria-hidden />
            AI agent for teachers
          </p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
            KlassenPilot
          </h1>
          <p className="mt-3 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            The self-improving executive assistant for every teacher.
          </p>

          <div className="mt-6 inline-flex max-w-full flex-col gap-2.5">
            <div
              className="grid w-full grid-cols-2 gap-2 sm:grid-cols-4"
              role="list"
              aria-label="What you can do"
            >
              {CAPABILITIES.map(({ label, Icon, title }) => (
                <span key={label} role="listitem" title={title} className={chipClassName}>
                  <Icon className="size-3.5 shrink-0 text-foreground" strokeWidth={2} aria-hidden />
                  {label}
                </span>
              ))}
            </div>
            <p
              className="whitespace-nowrap text-[11px] leading-relaxed tracking-wide text-muted-foreground sm:text-xs"
              title="How the agent is built"
            >
              GPT-5.6 · self-improving · curated memory · human-in-the-loop safeguards
            </p>
          </div>

          <div className="mt-8 flex flex-col gap-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-3 sm:gap-y-2">
              <Button asChild>
                <Link href="#your-classes-heading">
                  Explore your classes
                  <ArrowRight className="size-3.5" aria-hidden />
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/dev/how-to">How it works (1 min)</Link>
              </Button>
            </div>
            <Button asChild variant="outline"><Link href="#your-classes-heading" onClick={onCreateClass}>Create your own class</Link></Button>
          </div>
        </div>

        <div className="mt-6 flex justify-center md:absolute md:right-2 md:top-4 md:mt-0 md:justify-end">
          <AgentMark size={118} alive title="EEEck, KlassenPilot agent" />
        </div>
      </header>

      <section
        aria-labelledby="beta-heading"
        className="mt-12 border-t border-border pt-10 sm:mt-14 sm:pt-12"
      >
        <div className="grid gap-10 lg:grid-cols-2 lg:gap-12 lg:items-start">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Beta sandbox
            </p>
            <h2
              id="beta-heading"
              className="mt-2 text-2xl font-semibold tracking-tight text-foreground sm:text-[1.65rem]"
            >
              Try the demo or bring your own class.
            </h2>
            <p className="mt-3 max-w-md text-sm leading-relaxed text-muted-foreground sm:text-[0.95rem]">
              Beta workspaces can include a seeded chemistry playground. You can also create
              your own Chemie 8/9 NTG class and add your materials now.
            </p>
            <Link
              href="/docs/first-session"
              className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-foreground underline underline-offset-4 decoration-border hover:decoration-foreground"
            >
              See what to try
              <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          </div>

          <div className="flex flex-col gap-3">
            <Link
              href="#your-classes-heading"
              className="w-full rounded-xl border border-border bg-card/90 text-left shadow-sm transition-colors hover:border-foreground/25 hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <div className="p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-semibold text-foreground">Explore a class</h3>
                  <Badge variant="default" className="h-5 rounded-full px-2 text-[10px]">
                    Beta
                  </Badge>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  Open an available class below. Seeded demo classes include a lesson timeline, memory, and examples to explore.
                </p>
              </div>
            </Link>

            <div
              className="rounded-xl border border-border bg-card p-5"
            >
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-base font-semibold text-foreground">Your class</h3>
                <Badge variant="outline" className="h-5 rounded-full px-2 text-[10px]">
                  Available now
                </Badge>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                Start with an empty teaching history, review the curriculum map, and add your own PDFs.
              </p>
              <Button asChild variant="outline" className="mt-3"><Link href="#your-classes-heading" onClick={onCreateClass}>Start a new class</Link></Button>
            </div>
          </div>
        </div>
      </section>

      <section
        aria-labelledby="build-heading"
        className="mt-10 border-t border-border pt-10 sm:mt-12 sm:pt-12"
      >
        <Card variant="highlight" className="shadow-sm">
          <CardContent className="flex flex-col gap-5 p-6 sm:flex-row sm:items-center sm:justify-between sm:gap-8 sm:p-7">
            <div className="min-w-0 max-w-lg">
              <h2
                id="build-heading"
                className="text-xl font-semibold tracking-tight text-foreground"
              >
                Help build KlassenPilot
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                Real teachers, real pain points. We ship fast, listen, and put your input into the
                next version.
              </p>
            </div>
            <Button asChild variant="outline" className="shrink-0 self-start sm:self-center">
              <Link href="/beta/feedback">Give feedback</Link>
            </Button>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
