"use client";

import Link from "next/link";
import { Loader2Icon, XIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { chatRunningTaskLabel } from "@/lib/chat-run-feedback";
import { runningJobHref, type RunningJob } from "@/lib/running-jobs";

export function RunningTasksBox({
  jobs,
  onDismiss,
}: {
  jobs: RunningJob[];
  onDismiss: () => void;
}) {
  if (jobs.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 left-4 z-40 w-[min(20rem,calc(100vw-2rem))] rounded-lg border border-border bg-card p-2 shadow-sm"
      role="status"
      aria-live="polite"
    >
      <div className="mb-1.5 flex items-center justify-between gap-2 px-1">
        <p className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
          Running
        </p>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label="Hide running tasks"
          onClick={onDismiss}
        >
          <XIcon />
        </Button>
      </div>
      <ul className="overflow-hidden rounded-md border border-foreground/25 divide-y divide-foreground/25">
        {jobs.map((job, index) => (
          <li key={job.key} className={index % 2 === 0 ? "bg-card" : "bg-muted"}>
            <Link
              href={runningJobHref(job)}
              className="flex items-start gap-2 px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
            >
              <span className="mt-px w-4 shrink-0 tabular-nums text-foreground/70">
                {index + 1}.
              </span>
              <Loader2Icon className="mt-0.5 size-3.5 shrink-0 animate-spin" />
              <span className="leading-snug">
                {chatRunningTaskLabel({
                  mode: job.mode,
                  lessonDate: job.lessonDate,
                  lessonTitle: job.lessonTitle,
                })}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
