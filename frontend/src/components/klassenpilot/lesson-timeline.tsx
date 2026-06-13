"use client";

import { format, parseISO } from "date-fns";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { TimelineEntry } from "@/lib/api";
import { cn } from "@/lib/utils";

function monthLabel(monthKey: string): string {
  try {
    return format(parseISO(`${monthKey}-01`), "MMMM yyyy");
  } catch {
    return monthKey;
  }
}

function groupByMonth(entries: TimelineEntry[]): Map<string, TimelineEntry[]> {
  const map = new Map<string, TimelineEntry[]>();
  for (const entry of entries) {
    const key = entry.month_key || entry.date.slice(0, 7);
    const list = map.get(key) ?? [];
    list.push(entry);
    map.set(key, list);
  }
  return map;
}

export function LessonTimeline({
  classId,
  entries = [],
  months,
  highlightDate,
}: {
  classId: string;
  entries?: TimelineEntry[];
  months?: string[];
  highlightDate?: string | null;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const safeEntries = entries ?? [];
  const grouped = useMemo(() => groupByMonth(safeEntries), [safeEntries]);
  const monthKeys = useMemo(() => {
    const fromApi = months ?? [];
    return fromApi.length > 0 ? fromApi : [...grouped.keys()].sort().reverse();
  }, [months, grouped]);
  const [activeMonth, setActiveMonth] = useState("");

  const selectMonth = activeMonth || monthKeys[0] || "";

  const scrollToMonth = (monthKey: string) => {
    setActiveMonth(monthKey);
    const el = scrollRef.current?.querySelector(`#month-${monthKey}`);
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  if (safeEntries.length === 0) {
    return <p className="text-muted-foreground">No lessons logged yet.</p>;
  }

  return (
    <div className="space-y-3">
      {monthKeys.length > 1 && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Jump to month</span>
          <Select value={selectMonth} onValueChange={scrollToMonth}>
            <SelectTrigger className="h-8 w-[180px]">
              <SelectValue placeholder="Select month" />
            </SelectTrigger>
            <SelectContent>
              {monthKeys.map((m) => (
                <SelectItem key={m} value={m}>
                  {monthLabel(m)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <div
        ref={scrollRef}
        className="max-h-[min(70vh,32rem)] overflow-y-auto scroll-smooth pr-1"
      >
        <ol className="relative ml-3 space-y-8 border-l border-border pb-2">
          {monthKeys.map((monthKey) => {
            const monthEntries = grouped.get(monthKey) ?? [];
            if (monthEntries.length === 0) return null;
            return (
              <li key={monthKey} id={`month-${monthKey}`} className="list-none">
                <div className="sticky top-0 z-10 -ml-3 mb-4 border-b border-border bg-background/95 py-2 pl-6 backdrop-blur">
                  <h3 className="text-sm font-semibold text-foreground">{monthLabel(monthKey)}</h3>
                  <p className="text-xs text-muted-foreground">
                    {monthEntries.length} lesson{monthEntries.length === 1 ? "" : "s"}
                  </p>
                </div>
                <ul className="space-y-4">
                  {monthEntries.map((entry) => (
                    <LessonTimelineCard
                      key={entry.date}
                      classId={classId}
                      entry={entry}
                      highlighted={highlightDate === entry.date}
                    />
                  ))}
                </ul>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

function LessonTimelineCard({
  classId,
  entry,
  highlighted,
}: {
  classId: string;
  entry: TimelineEntry;
  highlighted?: boolean;
}) {
  return (
    <li className="ml-6 list-none">
      <span
        className={cn(
          "absolute -left-1.5 mt-3 h-3 w-3 rounded-full",
          entry.status === "planned" ? "border-2 border-primary bg-background" : "bg-primary",
        )}
      />
      <Card
        className={cn(
          "transition hover:border-primary/30 hover:shadow-sm",
          highlighted && "border-primary/50 ring-1 ring-primary/20",
        )}
      >
        <CardContent className="p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <time className="text-xs text-muted-foreground" dateTime={entry.date}>
                  {entry.date}
                </time>
                <h4 className="text-base font-semibold">{entry.title}</h4>
              </div>
              <div className="flex flex-wrap gap-1">
                {highlighted && (
                  <Badge variant="default" className="text-xs">
                    Just saved
                  </Badge>
                )}
                {entry.status === "planned" ? (
                  <Badge variant="secondary" className="text-xs">
                    Planned
                  </Badge>
                ) : (
                  entry.has_plan && (
                    <Badge variant="outline" className="text-xs">
                      Has plan
                    </Badge>
                  )
                )}
              </div>
            </div>
            {entry.summary && (
              <p className="mt-2 text-sm leading-snug text-muted-foreground">{entry.summary}</p>
            )}
            {entry.highlights.length > 0 && (
              <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
                {entry.highlights.map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button asChild size="sm" variant={entry.status === "planned" ? "default" : "outline"}>
                <Link
                  href={`/classes/${classId}/memory?lessonDate=${encodeURIComponent(
                    entry.date,
                  )}&intent=${
                    entry.status === "planned" ? "update_missing_results" : "correct_existing_results"
                  }&targetKind=${
                    entry.status === "planned" ? "planned_lesson" : "taught_lesson"
                  }&lessonTitle=${encodeURIComponent(entry.title)}`}
                >
                  {entry.status === "planned" ? "Add results" : "Correct with agent"}
                </Link>
              </Button>
              <Button asChild size="sm" variant="ghost">
                <Link href={`/classes/${classId}/lessons/${entry.date}`}>View details</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
    </li>
  );
}

export function MisconceptionsPanel({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <Card variant="highlight">
      <CardContent className="p-4">
        <h2 className="mb-2 font-semibold text-foreground">Top misconceptions</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          {items.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
