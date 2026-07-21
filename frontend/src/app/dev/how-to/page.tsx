"use client";

import Link from "next/link";

import { AgentMark, EEEck } from "@/components/klassenpilot/agent-mark";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const WORKFLOWS = [
  {
    key: "plan",
    title: "Create lesson plan",
    mark: <AgentMark boxSize={72} workflow="plan" title="EEEck · Plan" />,
    blurb:
      "Start with rough ideas for the next lesson. Chat back and forth until the draft feels right (the assistant does most of the drafting, using the adapted K–12 procedure plus LehrplanPLUS/KMK grounding). Then save it to a date.",
  },
  {
    key: "memory",
    title: "Update memory",
    mark: <AgentMark boxSize={72} workflow="memory" title="EEEck · Update memory" />,
    blurb:
      "Start with what happened after class in everyday language. Refine together into a structured write-up, then approve and save the notebook updates.",
  },
  {
    key: "discuss",
    title: "Discuss",
    mark: <EEEck boxSize={72} title="EEEck · Discuss" />,
    blurb:
      "Ask messy questions and keep going until the answer is useful. Class context stays in play; the notebook isn’t rewritten here.",
  },
  {
    key: "sweep",
    title: "Sharpen assistant",
    mark: <AgentMark boxSize={72} workflow="sweep" title="EEEck · Memory Sweep" />,
    blurb:
      "Review what the assistant picked up about how you like to work. Apply, skip, or postpone. Gets more personal only when you say yes.",
  },
] as const;

export default function DevHowToPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-8 pb-12">
      <PageHeader
        backHref="/"
        backLabel="Back to home"
        title="How it works"
        description="One-minute overview for someone new to KlassenPilot."
      />

      {/* 1) Large intro — two columns */}
      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border pb-4">
          <CardTitle className="text-xl font-semibold tracking-tight sm:text-2xl">
            A private assistant for one class
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            KlassenPilot is an executive assistant for a Gymnasium class, not a
            chatbot that forgets when you close the tab.
          </p>
        </CardHeader>
        <CardContent className="grid gap-8 p-6 sm:grid-cols-2 sm:gap-10 sm:p-8">
          <div className="space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
              How it works
            </h2>
            <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-foreground">
              <li>
                You chat; the assistant already knows this class’s notebook
                (lessons, open loops, what students struggle with).
              </li>
              <li>
                That notebook is private notes for the class: plans, results,
                students, follow-ups.
              </li>
              <li>
                While you work, it can also pick up how you like to teach and
                plan. Those ideas only stick when you approve them in Sharpen.
              </li>
              <li>
                Every approved update makes the next plan and the next question
                better.
              </li>
            </ul>
          </div>
          <div className="space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
              How it’s structured
            </h2>
            <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-foreground">
              <li>
                <span className="font-medium">Class home:</span> overview,
                actions, and a lesson timeline (Upcoming / Add results / Done).
              </li>
              <li>
                <span className="font-medium">Four jobs:</span> Plan, Update
                memory, Discuss, Sharpen. Same helper (EEEck); different tasks.
              </li>
              <li>
                <span className="font-medium">You stay in control:</span> class
                notebook updates when you save; assistant “learns” only after
                you approve in Sharpen.
              </li>
              <li>
                <span className="font-medium">Plan & Discuss:</span> help you
                think and draft; they don’t rewrite the notebook by themselves.
              </li>
              <li>
                <span className="font-medium">Curriculum grounding:</span>{" "}
                Planning uses adapted open K–12 skills (Anthropic) and
                LehrplanPLUS/KMK trusted sources. Frameworks are curated
                pedagogy for Chemie 9 NTG (shared 8/9).
              </li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* Class notebook vs what the assistant learns */}
      <Card>
        <CardHeader className="border-b border-border pb-4">
          <CardTitle className="text-xl font-semibold tracking-tight sm:text-2xl">
            Two kinds of notes
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Think of a private class binder, plus a short list of how you like
            to work with the assistant.
          </p>
        </CardHeader>
        <CardContent className="grid gap-6 p-5 sm:grid-cols-2 sm:gap-8 sm:p-6">
          <div className="space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
              Class notebook
            </h2>
            <p className="text-sm text-muted-foreground">
              The facts of this class. Written when you save Update memory or a
              lesson plan.
            </p>
            <pre className="overflow-x-auto rounded-lg border border-border bg-muted/50 p-3 font-mono text-[11px] leading-relaxed text-foreground sm:text-xs">
{`class/
  lessons/{date}/
    plan          ← what you’ll teach
    results       ← what you taught
  students/       ← observations
  timeline
  open loops
  misconceptions`}
            </pre>
          </div>
          <div className="space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
              What the assistant learns
            </h2>
            <p className="text-sm text-muted-foreground">
              How <em>you</em> and <em>this class</em> like to work. Gathered
              while you chat; applied only when you approve in Sharpen.
            </p>
            <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-foreground">
              <li>
                <span className="font-medium">Your preferences:</span> tone,
                plan length, “always start with a 5‑min review,” etc.
              </li>
              <li>
                <span className="font-medium">How this class learns:</span> what
                scaffolds and formats actually work here.
              </li>
              <li>
                <span className="font-medium">Working rules for the assistant:</span>{" "}
                what to avoid, how to plan for Chemie 9b.
              </li>
            </ul>
            <p className="text-xs text-muted-foreground">
              Chat can stage these; nothing sticks until you say yes.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 2×2 workflows */}
      <Card>
        <CardHeader className="border-b border-border pb-4">
          <CardTitle className="text-xl font-semibold tracking-tight sm:text-2xl">
            The four workflows
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Start rough, refine in chat; the assistant does most of the drafting.
            Sharpen is where you approve what it learned about you.
          </p>
        </CardHeader>
        <CardContent className="grid gap-6 p-5 sm:grid-cols-2 sm:gap-8 sm:p-6">
          {WORKFLOWS.map((w) => (
            <div key={w.key} className="flex gap-4">
              <div className="shrink-0 pt-0.5">{w.mark}</div>
              <div className="min-w-0 space-y-1">
                <h3 className="text-base font-semibold text-foreground">{w.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {w.blurb}
                </p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* 3) So what + key callouts */}
      <Card variant="highlight">
        <CardContent className="grid gap-6 p-5 sm:grid-cols-2 sm:gap-8 sm:p-6">
          <div className="space-y-2">
            <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
              So what
            </h2>
            <p className="text-sm font-medium leading-relaxed text-foreground">
              You stop starting from a blank prompt. The assistant already knows
              this class, and gets better every time you approve a memory write.
            </p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Time saved is the north star: less “work about work,” more time with
              students.
            </p>
          </div>
          <div className="space-y-2">
            <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
              Key callouts
            </h2>
            <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-foreground">
              <li>
                <span className="font-medium">Teacher stays in control:</span> no
                silent notebook edits from chat.
              </li>
              <li>
                <span className="font-medium">Class notebook = the record:</span>{" "}
                chat is how you talk; approved saves are what sticks.
              </li>
              <li>
                <span className="font-medium">“Learns about you” → Sharpen:</span>{" "}
                staged while you chat; you decide later.
              </li>
              <li>
                <span className="font-medium">After you save a lesson:</span> short
                “saved” moment, then back to class home with that lesson
                highlighted.
              </li>
            </ul>
          </div>
        </CardContent>
      </Card>

      <p className="text-center text-sm text-muted-foreground">
        <Link href="/" className="text-primary hover:underline">
          Back to home
        </Link>
        {" · "}
        <Link href="/docs" className="text-primary hover:underline">
          Full docs
        </Link>
      </p>
    </div>
  );
}
