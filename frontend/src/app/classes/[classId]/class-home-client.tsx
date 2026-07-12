"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ActionLink } from "@/components/klassenpilot/action-link";
import {
  LessonTimeline,
  MisconceptionsPanel,
} from "@/components/klassenpilot/lesson-timeline";
import { StatCard } from "@/components/klassenpilot/stat-card";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  client,
  type ClassMemorySnapshot,
  type ClassTimeline,
  type MemorySweepReviewResponse,
} from "@/lib/api";
import { consumeClassHomeTimelineRefresh } from "@/lib/class-home-refresh";
import { memorySweepReviewBadge } from "@/lib/memory-sweep-review-status";

type ClassHomeClientProps = {
  classId: string;
  highlightDate?: string;
};

function emptySnapshot(classId: string): ClassMemorySnapshot {
  return {
    class_id: classId,
    label: classId,
    current_unit: "-",
    open_loop_count: 0,
    top_misconceptions: [],
    recent_lessons: [],
  };
}

export function ClassHomeClient({ classId, highlightDate }: ClassHomeClientProps) {
  const [timeline, setTimeline] = useState<ClassTimeline>({
    class_id: classId,
    entries: [],
    months: [],
  });
  const [snapshot, setSnapshot] = useState<ClassMemorySnapshot>(
    emptySnapshot(classId),
  );
  const [memorySweepReview, setMemorySweepReview] =
    useState<MemorySweepReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchClassHome = useCallback(
    async (opts?: { snapshot?: boolean }) => {
      const includeSnapshot = opts?.snapshot !== false;
      const requests = includeSnapshot
        ? Promise.all([
            client.getTimeline(classId),
            client.getSnapshot(classId),
            client.getMemorySweepReview(classId),
          ])
        : Promise.all([
            client.getTimeline(classId),
            client.getMemorySweepReview(classId),
          ]).then(([timelineData, reviewData]) => [timelineData, null, reviewData] as const);

      const [timelineData, snapshotData, reviewData] = await requests;
      return { timelineData, snapshotData, reviewData };
    },
    [classId],
  );

  useEffect(() => {
    let cancelled = false;
    fetchClassHome()
      .then(({ timelineData, snapshotData, reviewData }) => {
        if (!cancelled) {
          setTimeline(timelineData);
          if (snapshotData) setSnapshot(snapshotData);
          setMemorySweepReview(reviewData);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load class");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [fetchClassHome]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const refreshIfMarked = () => {
      if (!consumeClassHomeTimelineRefresh(window.sessionStorage, classId)) return;
      void fetchClassHome({ snapshot: false })
        .then(({ timelineData, reviewData }) => {
          setTimeline(timelineData);
          setMemorySweepReview(reviewData);
          setError(null);
        })
        .catch((e: unknown) => {
          setError(e instanceof Error ? e.message : "Failed to refresh timeline");
        });
    };

    const refreshReviewStatus = () => {
      void client
        .getMemorySweepReview(classId)
        .then(setMemorySweepReview)
        .catch(() => {
          // Keep the rest of class home usable if the badge status fails.
        });
    };

    const handlePageResume = () => {
      refreshIfMarked();
      refreshReviewStatus();
    };

    const handleVisibility = () => {
      if (document.visibilityState === "visible") handlePageResume();
    };

    window.addEventListener("pageshow", handlePageResume);
    window.addEventListener("focus", handlePageResume);
    document.addEventListener("visibilitychange", handleVisibility);
    refreshIfMarked();
    refreshReviewStatus();
    return () => {
      window.removeEventListener("pageshow", handlePageResume);
      window.removeEventListener("focus", handlePageResume);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [classId, fetchClassHome]);

  const timelineEntries = timeline.entries ?? [];
  const timelineMonths = timeline.months ?? [];
  const memorySweepBadge = memorySweepReviewBadge(memorySweepReview);

  return (
    <div>
      <PageHeader
        title={snapshot.label}
        description={`Current unit: ${snapshot.current_unit}`}
      />

      {error && (
        <Alert className="mb-6 border-border bg-muted text-foreground">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="mb-8 grid gap-4 sm:grid-cols-3">
        <StatCard label="Open loops" value={String(snapshot.open_loop_count)} />
        <StatCard
          label="Last saved"
          value={
            snapshot.last_committed_date
              ? snapshot.last_committed_title
                ? `${snapshot.last_committed_date} - ${snapshot.last_committed_title}`
                : snapshot.last_committed_date
              : (snapshot.last_lesson_date ?? "-")
          }
        />
        <StatCard label="Lessons logged" value={String(timeline.entries.length)} />
      </div>

      <MisconceptionsPanel items={snapshot.top_misconceptions} />

      <div className="mb-10 mt-8 flex flex-wrap gap-3">
        <ActionLink href={`/classes/${classId}/memory`} primary>
          Update memory
        </ActionLink>
        <ActionLink href={`/classes/${classId}/plan`}>Create lesson plan</ActionLink>
        <ActionLink href={`/classes/${classId}/memory-sweep`}>
          <span className="flex flex-col items-start leading-tight">
            <span>Memory Sweep</span>
            {memorySweepBadge && (
              <span className="text-xs font-normal opacity-80">
                {memorySweepBadge}
              </span>
            )}
          </span>
        </ActionLink>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Lesson timeline</CardTitle>
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-sm text-muted-foreground">
              Timeline unavailable until the API loads successfully.
            </p>
          ) : (
            <LessonTimeline
              classId={classId}
              entries={timelineEntries}
              months={timelineMonths}
              highlightDate={highlightDate ?? snapshot.last_committed_date}
            />
          )}
        </CardContent>
      </Card>

      <p className="mt-6 text-sm text-muted-foreground">
        <Link href="/" className="text-primary hover:underline">
          All classes
        </Link>
      </p>
    </div>
  );
}
