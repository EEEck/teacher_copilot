"use client";

import React, { useEffect, useState } from "react";
import { LoaderCircleIcon } from "lucide-react";

import { ReviewChrome } from "@/components/klassenpilot/review/review-chrome";
import { Badge } from "@/components/ui/badge";
import { client } from "@/lib/api";

export type PlanVerificationRow = {
  row_id: string;
  label: string;
  status: "clear" | "note" | "needs_teacher_decision";
  summary: string;
};

export type PlanVerificationReport = {
  overall_status: "clear" | "advisory" | "safety_hold";
  summary: string;
  review_state: "pending" | "complete" | "failed" | "stale";
  rows: PlanVerificationRow[];
};

function headline(report: PlanVerificationReport) {
  if (report.review_state === "pending") return { label: "Reviewing", variant: "outline" as const };
  if (report.review_state === "stale") return { label: "Review before save", variant: "outline" as const };
  if (report.review_state === "failed") return { label: "Review unavailable", variant: "outline" as const };
  if (report.overall_status === "safety_hold") return { label: "Safety hold", variant: "destructive" as const };
  if (report.overall_status === "advisory") return { label: "Teacher review", variant: "outline" as const };
  return { label: "Clear", variant: "default" as const };
}

function rowLabel(status: PlanVerificationRow["status"]) {
  if (status === "needs_teacher_decision") return "Teacher decision";
  if (status === "note") return "Note";
  return "Clear";
}

/** A compact runtime activity in the chat flow, not a synthetic chat message. */
export function PlanVerificationReportCard({ report }: { report: PlanVerificationReport }) {
  const status = headline(report);
  if (report.review_state === "pending") {
    return (
      <div role="status" className="flex items-center gap-2 px-2 py-1.5 text-sm text-muted-foreground">
        <LoaderCircleIcon className="size-4 animate-spin" />
        <span>Reviewing plan against curriculum, class context, and safety...</span>
      </div>
    );
  }

  return (
    <ReviewChrome>
      <details>
        <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm marker:hidden [&::-webkit-details-marker]:hidden">
          <Badge variant={status.variant}>{status.label}</Badge>
          <span className="min-w-0 flex-1 text-muted-foreground">
            <span className="font-medium text-foreground">Plan review ready.</span>{" "}
            {report.summary}
          </span>
          <span className="text-xs text-muted-foreground">Show details</span>
        </summary>
        {report.rows.length > 0 && (
          <ul className="space-y-2 border-t border-border px-3 py-2">
            {report.rows.map((row) => (
              <li key={row.row_id}>
                <p className="text-xs font-medium text-foreground">
                  {row.label} <span className="font-normal text-muted-foreground">- {rowLabel(row.status)}</span>
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">{row.summary}</p>
              </li>
            ))}
          </ul>
        )}
      </details>
    </ReviewChrome>
  );
}

function asReport(value: unknown): PlanVerificationReport | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  if (
    !["clear", "advisory", "safety_hold"].includes(String(raw.overall_status)) ||
    !["pending", "complete", "failed", "stale"].includes(String(raw.review_state)) ||
    !Array.isArray(raw.rows)
  ) {
    return null;
  }
  return raw as unknown as PlanVerificationReport;
}

export function PlanVerificationPanel({
  classId,
  sessionId,
  artifactRevision,
}: {
  classId: string;
  sessionId: string;
  artifactRevision: number;
}) {
  const [report, setReport] = useState<PlanVerificationReport | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    let timer: number | undefined;
    const refresh = async () => {
      try {
        const draft = await client.planGetDraft(classId, sessionId);
        const reports = draft.executive_state?.verification_reports;
        const next = asReport(
          reports && typeof reports === "object"
            ? (reports as Record<string, unknown>).plan
            : undefined,
        );
        if (cancelled) return;
        setReport(next);
        if (next?.review_state === "pending") {
          timer = window.setTimeout(() => void refresh(), 1_000);
        }
      } catch {
        // A missing advisory report must not disturb editing or saving the draft.
      }
    };
    void refresh();
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [classId, sessionId, artifactRevision]);

  return report ? <PlanVerificationReportCard report={report} /> : null;
}
