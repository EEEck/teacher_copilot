"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactElement,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { ActionCornerBadge } from "@/components/klassenpilot/action-corner-badge";
import { ActionLink } from "@/components/klassenpilot/action-link";
import { ClassHomeNotes } from "@/components/klassenpilot/class-home-notes";
import { ClassHomeSection } from "@/components/klassenpilot/class-home-section";
import {
  DiscussDock,
  type DiscussDockState,
} from "@/components/klassenpilot/discuss-dock";
import { LessonTimeline } from "@/components/klassenpilot/lesson-timeline";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StickyNote } from "@/components/ui/sticky-note";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  client,
  type ClassBrief,
  type ClassMemorySnapshot,
  type ClassTimeline,
  type MemorySweepReviewResponse,
} from "@/lib/api";
import {
  CLASS_HOME_HOVER,
  classHomeLessonProgress,
  formatClassHomeHeading,
  shortenUnitLabel,
} from "@/lib/class-home-display";
import { consumeClassHomeTimelineRefresh } from "@/lib/class-home-refresh";
import { classHomeWatchItems } from "@/lib/class-home-watch";
import { shortWikiPath } from "@/lib/markdown-diff";
import {
  memorySweepDueBadge,
  memorySweepReviewAttentionBadge,
  memorySweepUsefulSubtitle,
} from "@/lib/memory-sweep-review-status";
import { workflowDraftCornerBadge } from "@/lib/workflow-draft-badge";
import {
  normalizeClassWikiPath,
  wikiViewerHref,
} from "@/lib/wiki-viewer-links";

function WorkflowHover({
  label,
  children,
}: {
  label: string;
  children: ReactElement;
}) {
  return (
    <Tooltip>
      {/* Span wrapper: reliable hover target (Next Link + asChild is fragile). */}
      <TooltipTrigger asChild>
        <span className="inline-flex w-full min-w-0">{children}</span>
      </TooltipTrigger>
      <TooltipContent
        side="bottom"
        className="max-w-sm text-pretty leading-relaxed"
      >
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

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
  const [showActionsHelp, setShowActionsHelp] = useState(true);
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
  const memorySweepSubtitle = memorySweepUsefulSubtitle(memorySweepReview);
  const memorySweepQuietSubtitle = memorySweepSubtitle.startsWith("Draft saved")
    ? memorySweepSubtitle
    : "";
  const memorySweepAttention = memorySweepReviewAttentionBadge(
    memorySweepReview,
  );
  const memorySweepDue = memorySweepDueBadge(memorySweepReview);
  // Chip = attention (4) or weekly due; quiet draft stays as subtitle (2).
  const memorySweepChip = memorySweepAttention || memorySweepDue;
  const planDraftChip = workflowDraftCornerBadge(timeline.active_plan_draft);
  const memoryDraftChip = workflowDraftCornerBadge(timeline.active_memory_draft);

  const watchItems = useMemo(
    () =>
      classHomeWatchItems(snapshot.top_misconceptions, brief?.watch_items),
    [snapshot.top_misconceptions, brief?.watch_items],
  );
  const briefReasons = (brief?.reasons ?? []).slice(0, 3);
  // No wiki-backed source for key dates yet (assessment calendar is a later
  // backlog item); render an honest empty state until one exists.
  const upcoming: { label: string; date: string }[] = [];
  const { lastTaught, lessonsLogged } = classHomeLessonProgress(timelineEntries);
  const heading = useMemo(
    () => formatClassHomeHeading(classId, snapshot.label),
    [classId, snapshot.label],
  );
  const unitShort = shortenUnitLabel(snapshot.current_unit || "");
  const headerDescription = [heading.year, heading.track]
    .filter(Boolean)
    .join(" · ");

  return (
    <TooltipProvider delayDuration={250}>
    <div>
      <PageHeader
        title={heading.title}
        description={headerDescription || undefined}
      />

      {error && (
        <Alert className="mb-6 border-border bg-muted text-foreground">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <ClassHomeSection
        id="classroom-dashboard"
        title="Classroom dashboard"
        description="Your class at a glance: brief, metrics, upcoming dates, and local notes."
      >
        <Card className="mb-4" variant="highlight">
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
            {briefReasons.length ? (
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {briefReasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : null}
            {watchItems.length ? (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Watch
                </p>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                  {watchItems.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
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

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader className="pb-0">
              <CardTitle className="text-base">At a glance</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-5">
                <div>
                  <dt className="text-sm text-muted-foreground">Unit</dt>
                  <dd
                    className="mt-1 text-xl font-semibold leading-snug tracking-tight text-foreground"
                    title={snapshot.current_unit || undefined}
                  >
                    {unitShort}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm text-muted-foreground">Open loops</dt>
                  <dd className="mt-1 text-2xl font-semibold tabular-nums tracking-tight text-foreground">
                    {snapshot.open_loop_count}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm text-muted-foreground">Last taught</dt>
                  <dd className="mt-1 text-xl font-semibold tabular-nums tracking-tight text-foreground">
                    {lastTaught}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm text-muted-foreground">Lessons logged</dt>
                  <dd className="mt-1 text-2xl font-semibold tabular-nums tracking-tight text-foreground">
                    {lessonsLogged}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-0">
              <CardTitle className="text-base">Upcoming</CardTitle>
            </CardHeader>
            <CardContent>
              {upcoming.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No key dates yet.
                </p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {upcoming.map((item) => (
                    <li
                      key={`${item.label}-${item.date}`}
                      className="flex items-baseline justify-between gap-3"
                    >
                      <span className="text-foreground">{item.label}</span>
                      <span className="shrink-0 tabular-nums text-muted-foreground">
                        {item.date}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <div className="md:col-span-2">
            <ClassHomeNotes classId={classId} />
          </div>
        </div>
      </ClassHomeSection>

      <ClassHomeSection
        id="actions"
        title="Actions"
        description="Pick one job at a time for this class."
      >
        {showActionsHelp && (
          <StickyNote
            className="mb-4"
            title="What you can do"
            dismissAriaLabel="Dismiss actions help"
            onDismiss={() => setShowActionsHelp(false)}
          >
            <ul className="list-disc space-y-1 pl-5">
              <li>
                <span className="font-medium">Create lesson plan:</span> draft
                the next lesson or assessment from class memory.
              </li>
              <li>
                <span className="font-medium">Discuss:</span> ask about open
                loops, watch items, or what to do next (opens the chat dock).
              </li>
              <li>
                <span className="font-medium">Sharpen assistant:</span>{" "}
                review quiet insights so it gets more personal for this class.
                Aim for about once a week; we nudge after 5 days.
              </li>
              <li>
                <span className="font-medium">Other wiki edits:</span> freeform
                wiki changes when you are not starting from a lesson card.
                After teaching, prefer{" "}
                <span className="font-medium">Add results</span> on the
                timeline.
              </li>
              <li>
                <span className="font-medium">Browse class files:</span> open
                the living notebook for this class (lesson notes, plans, and
                memory).
              </li>
            </ul>
          </StickyNote>
        )}

        {/* Equal width = widest label; Plan first among core workflows. */}
        <div
          className="inline-grid max-w-full grid-flow-col auto-cols-[1fr] items-stretch gap-3"
          role="group"
          aria-label="Class workflows"
        >
          <WorkflowHover label={CLASS_HOME_HOVER.plan}>
            <ActionLink
              href={`/classes/${classId}/plan`}
              variant="soft"
              size="lg"
              className="relative w-full justify-center px-3"
            >
              Create lesson plan
              {planDraftChip ? (
                <ActionCornerBadge>{planDraftChip}</ActionCornerBadge>
              ) : null}
            </ActionLink>
          </WorkflowHover>
          <WorkflowHover label={CLASS_HOME_HOVER.discuss}>
            <Button
              type="button"
              variant="soft"
              size="lg"
              className="w-full justify-center px-3"
              onClick={() => setDiscussDock("expanded")}
            >
              Discuss
            </Button>
          </WorkflowHover>
          <WorkflowHover label={CLASS_HOME_HOVER.sweep}>
            <ActionLink
              href={`/classes/${classId}/memory-sweep`}
              variant="outline"
              size="lg"
              className="relative w-full flex-col justify-center gap-0 px-3 leading-tight"
            >
              <span>Sharpen assistant</span>
              {memorySweepQuietSubtitle ? (
                <span className="text-[10px] font-normal text-muted-foreground">
                  {memorySweepQuietSubtitle}
                </span>
              ) : null}
              {memorySweepChip ? (
                <ActionCornerBadge
                  tone={memorySweepAttention ? "neutral" : "attention"}
                >
                  {memorySweepChip}
                </ActionCornerBadge>
              ) : null}
            </ActionLink>
          </WorkflowHover>
          <WorkflowHover label={CLASS_HOME_HOVER.memory}>
            <ActionLink
              href={`/classes/${classId}/memory`}
              variant="outline"
              size="lg"
              className="relative w-full justify-center px-3"
            >
              Other wiki edits
              {memoryDraftChip ? (
                <ActionCornerBadge>{memoryDraftChip}</ActionCornerBadge>
              ) : null}
            </ActionLink>
          </WorkflowHover>
          <WorkflowHover label="Explore course concepts, curriculum, and teaching materials.">
            <ActionLink href={`/classes/${classId}/course`} variant="outline" size="lg" className="w-full justify-center px-3">
              Course
            </ActionLink>
          </WorkflowHover>
          <WorkflowHover label={CLASS_HOME_HOVER.wiki}>
            <ActionLink
              href={`/classes/${classId}/wiki/view`}
              variant="outline"
              size="lg"
              className="w-full justify-center px-3"
            >
              Browse class files
            </ActionLink>
          </WorkflowHover>
        </div>
      </ClassHomeSection>

      <DiscussDock
        classId={classId}
        state={discussDock}
        onStateChange={setDiscussDock}
      />

      <ClassHomeSection
        id="lesson-timeline"
        title="Lesson timeline"
        titleHover={CLASS_HOME_HOVER.timeline}
        description="Planned and taught lessons for this class."
      >
        <Card>
          <CardContent className="pt-6">
            {error ? (
              <p className="text-sm text-muted-foreground">
                Timeline unavailable until the API loads successfully.
              </p>
            ) : (
              <LessonTimeline
                classId={classId}
                entries={timelineEntries}
                months={timelineMonths}
                highlightDate={highlightDate}
                planHover={CLASS_HOME_HOVER.plan}
              />
            )}
          </CardContent>
        </Card>
      </ClassHomeSection>

      <p className="mt-2 text-sm text-muted-foreground">
        <Link href="/" className="text-primary hover:underline">
          All classes
        </Link>
      </p>
    </div>
    </TooltipProvider>
  );
}
