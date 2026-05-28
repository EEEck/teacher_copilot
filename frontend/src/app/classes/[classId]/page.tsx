import Link from "next/link";
import { ActionLink } from "@/components/klassenpilot/action-link";
import { LessonTimeline, MisconceptionsPanel } from "@/components/klassenpilot/lesson-timeline";
import { StatCard } from "@/components/klassenpilot/stat-card";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { client, type ClassMemorySnapshot, type ClassTimeline } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ClassHomePage({
  params,
  searchParams,
}: {
  params: Promise<{ classId: string }>;
  searchParams: Promise<{ highlight?: string }>;
}) {
  const { classId } = await params;
  const { highlight: highlightDate } = await searchParams;
  let timeline: ClassTimeline = { class_id: classId, entries: [], months: [] };
  let snapshot: ClassMemorySnapshot = {
    class_id: classId,
    label: classId,
    current_unit: "—",
    open_loop_count: 0,
    top_misconceptions: [],
    recent_lessons: [],
  };
  let error: string | null = null;
  try {
    [timeline, snapshot] = await Promise.all([
      client.getTimeline(classId),
      client.getSnapshot(classId),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load class";
  }

  const timelineEntries = timeline.entries ?? [];
  const timelineMonths = timeline.months ?? [];

  return (
    <div>
      <PageHeader title={snapshot.label} description={`Current unit: ${snapshot.current_unit}`} />

      {error && (
        <Alert className="mb-6 border-border bg-muted text-foreground">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="mb-8 grid gap-4 sm:grid-cols-3">
        <StatCard label="Open loops" value={String(snapshot.open_loop_count)} />
        <StatCard
          label="Last saved"
          value={snapshot.last_committed_date ?? snapshot.last_lesson_date ?? "—"}
        />
        <StatCard label="Lessons logged" value={String(timeline.entries.length)} />
      </div>

      <MisconceptionsPanel items={snapshot.top_misconceptions} />

      <div className="mb-10 mt-8 flex flex-wrap gap-3">
        <ActionLink href={`/classes/${classId}/memory`} primary>
          Update memory
        </ActionLink>
        <ActionLink href={`/classes/${classId}/plan`}>Create lesson plan</ActionLink>
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
          ← All classes
        </Link>
      </p>
    </div>
  );
}
