"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { ActionLink } from "@/components/klassenpilot/action-link";
import {
  DiscussDock,
  type DiscussDockState,
} from "@/components/klassenpilot/discuss-dock";
import {
  LessonTimeline,
  MisconceptionsPanel,
} from "@/components/klassenpilot/lesson-timeline";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  client,
  type ClassBrief,
  type ClassMemorySnapshot,
  type ClassTimeline,
  type MemorySweepReviewResponse,
} from "@/lib/api";
import { consumeClassHomeTimelineRefresh } from "@/lib/class-home-refresh";
import { shortWikiPath } from "@/lib/markdown-diff";
import { memorySweepReviewBadge } from "@/lib/memory-sweep-review-status";
import {
  normalizeClassWikiPath,
  wikiViewerHref,
} from "@/lib/wiki-viewer-links";

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

function wikiHref(classId: string, path: string): string {
  return wikiViewerHref(classId, normalizeClassWikiPath(classId, path));
}

export function ClassHomeClient({ classId, highlightDate }: ClassHomeClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [timeline, setTimeline] = useState<ClassTimeline>({
    class_id: classId,
    entries: [],
    months: [],
  });
  const [snapshot, setSnapshot] = useState<ClassMemorySnapshot>(
    emptySnapshot(classId),
  );
  const [brief, setBrief] = useState<ClassBrief | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [discussDock, setDiscussDock] = useState<DiscussDockState>("closed");
  const [memorySweepReview, setMemorySweepReview] =
    useState<MemorySweepReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Running-box / deep links: /classes/{id}?discuss=open → expand dock.
  useEffect(() => {
    if (searchParams.get("discuss") !== "open") return;
    setDiscussDock("expanded");
    const next = new URLSearchParams(searchParams.toString());
    next.delete("discuss");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [searchParams, router, pathname]);

  const fetchClassHome = useCallback(
    async (opts?: { snapshot?: boolean }) => {
      const includeSnapshot = opts?.snapshot !== false;
      const requests = includeSnapshot
        ? Promise.all([
            client.getTimeline(classId),
            client.getSnapshot(classId),
            client.getMemorySweepReview(classId),
            client.getClassBrief(classId),
          ])
        : Promise.all([
            client.getTimeline(classId),
            client.getMemorySweepReview(classId),
          ]).then(
            ([timelineData, reviewData]) =>
              [timelineData, null, reviewData, null] as const,
          );

      const [timelineData, snapshotData, reviewData, briefData] = await requests;
      return { timelineData, snapshotData, reviewData, briefData };
    },
    [classId],
  );

  useEffect(() => {
    let cancelled = false;
    fetchClassHome()
      .then(({ timelineData, snapshotData, reviewData, briefData }) => {
        if (!cancelled) {
          setTimeline(timelineData);
          if (snapshotData) setSnapshot(snapshotData);
          setMemorySweepReview(reviewData);
          if (briefData) setBrief(briefData);
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

  const refreshBrief = async () => {
    setBriefLoading(true);
    try {
      const next = await client.refreshClassBrief(classId);
      setBrief(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh brief");
    } finally {
      setBriefLoading(false);
    }
  };

  const timelineEntries = timeline.entries ?? [];
  const timelineMonths = timeline.months ?? [];
  const memorySweepBadge = memorySweepReviewBadge(memorySweepReview);
  const recommendedHref =
    brief?.recommended_action.href ||
    (brief?.recommended_action.label.toLowerCase().includes("memory sweep")
      ? `/classes/${classId}/memory-sweep`
      : brief?.recommended_action.label.toLowerCase().includes("update")
        ? `/classes/${classId}/memory`
        : `/classes/${classId}/plan`);

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

      <Card className="mb-8" variant="highlight">
        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
          <div>
            <CardTitle>Today&apos;s class brief</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              {brief?.cached
                ? "Cached briefing from the last refresh."
                : "Snapshot-backed briefing until you refresh."}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refreshBrief()}
            disabled={briefLoading}
          >
            {briefLoading ? "Refreshing…" : "Refresh brief"}
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm leading-relaxed text-foreground">
            {brief?.summary ?? "Loading class brief…"}
          </p>
          {brief?.reasons?.length ? (
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {brief.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
          {brief?.watch_items?.length ? (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Watch
              </p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {brief.watch_items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {brief?.recommended_action?.label ? (
            <ActionLink href={recommendedHref} primary>
              {brief.recommended_action.label}
            </ActionLink>
          ) : null}
          {brief?.source_paths?.length ? (
            <p className="text-xs text-muted-foreground">
              Based on{" "}
              {brief.source_paths.map((path, index) => (
                <span key={path}>
                  {index > 0 ? ", " : ""}
                  <Link
                    href={wikiHref(classId, path)}
                    className="text-primary hover:underline"
                  >
                    {shortWikiPath(path)}
                  </Link>
                </span>
              ))}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <MisconceptionsPanel items={snapshot.top_misconceptions} />

      <div className="mb-6 mt-8 flex flex-wrap gap-3">
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
        <ActionLink href={`/classes/${classId}/wiki/view`}>Inspect wiki</ActionLink>
      </div>

      <DiscussDock
        classId={classId}
        state={discussDock}
        onStateChange={setDiscussDock}
      />

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
