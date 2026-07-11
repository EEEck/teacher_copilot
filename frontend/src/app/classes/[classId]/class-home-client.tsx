"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { MessageSquare, RefreshCw, Send } from "lucide-react";

import { ActionLink } from "@/components/klassenpilot/action-link";
import {
  LessonTimeline,
} from "@/components/klassenpilot/lesson-timeline";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  client,
  type ClassBrief,
  type ClassBriefAction,
  type ClassMemorySnapshot,
  type ClassTimeline,
} from "@/lib/api";

type ClassHomeClientProps = {
  classId: string;
  highlightDate?: string;
};

type DiscussionMessage = {
  role: "user" | "assistant";
  content: string;
  sourcePaths?: string[];
  suggestedActions?: ClassBriefAction[];
  memoryCandidateCount?: number;
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

function emptyBrief(classId: string): ClassBrief {
  return {
    class_id: classId,
    summary: "Class briefing unavailable until the API loads class memory.",
    recommended_action: {
      label: "Update memory",
      href: `/classes/${classId}/memory`,
      rationale: "Start by capturing the latest class evidence.",
    },
    reasons: [],
    watch_items: [],
    source_paths: [],
    generated_at: "",
    cached: false,
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
  const [brief, setBrief] = useState<ClassBrief>(emptyBrief(classId));
  const [error, setError] = useState<string | null>(null);
  const [briefRefreshing, setBriefRefreshing] = useState(false);
  const [discussionOpen, setDiscussionOpen] = useState(false);
  const [discussionSessionId, setDiscussionSessionId] = useState<string | null>(null);
  const [discussionMessages, setDiscussionMessages] = useState<DiscussionMessage[]>([]);
  const [discussionInput, setDiscussionInput] = useState("");
  const [discussionSending, setDiscussionSending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      client.getTimeline(classId),
      client.getSnapshot(classId),
      client.getClassBrief(classId),
    ])
      .then(([timelineData, snapshotData, briefData]) => {
        if (!cancelled) {
          setTimeline(timelineData);
          setSnapshot(snapshotData);
          setBrief(briefData);
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
  }, [classId]);

  const timelineEntries = timeline.entries ?? [];
  const timelineMonths = timeline.months ?? [];

  const refreshBrief = async () => {
    setBriefRefreshing(true);
    try {
      const nextBrief = await client.refreshClassBrief(classId);
      setBrief(nextBrief);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to refresh class brief");
    } finally {
      setBriefRefreshing(false);
    }
  };

  const ensureDiscussionSession = async () => {
    if (discussionSessionId) return discussionSessionId;
    const session = await client.startClassDiscussion(classId);
    setDiscussionSessionId(session.session_id);
    return session.session_id;
  };

  const sendDiscussionMessage = async () => {
    const message = discussionInput.trim();
    if (!message || discussionSending) return;
    setDiscussionSending(true);
    setDiscussionInput("");
    setDiscussionMessages((items) => [...items, { role: "user", content: message }]);
    try {
      const sessionId = await ensureDiscussionSession();
      const response = await client.classDiscussionChat(classId, sessionId, message);
      setDiscussionMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: response.reply,
          sourcePaths: response.source_paths,
          suggestedActions: response.suggested_actions,
          memoryCandidateCount: response.memory_candidates.length,
        },
      ]);
      setError(null);
    } catch (e: unknown) {
      setDiscussionMessages((items) => [
        ...items,
        {
          role: "assistant",
          content:
            e instanceof Error
              ? e.message
              : "I could not answer that class-state question.",
        },
      ]);
    } finally {
      setDiscussionSending(false);
    }
  };

  return (
    <div>
      <PageHeader
        title={snapshot.label}
        description="Class briefing, memory actions, and lesson history."
      />

      {error && (
        <Alert className="mb-6 border-border bg-muted text-foreground">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className="mb-6">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>Today&apos;s class brief</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              Current unit: {snapshot.current_unit}
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={refreshBrief}
            disabled={briefRefreshing}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            {briefRefreshing ? "Refreshing..." : "Refresh brief"}
          </Button>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
            <div className="space-y-4">
              <p className="text-base leading-relaxed text-foreground">{brief.summary}</p>
              {brief.reasons.length > 0 && (
                <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                  {brief.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              )}
              {brief.source_paths.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {brief.source_paths.slice(0, 4).map((path) => (
                    <Badge key={path} variant="outline" className="max-w-full truncate">
                      {path}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
            <div className="space-y-3 rounded-md border border-border p-4">
              <p className="text-xs font-medium uppercase text-muted-foreground">
                Recommended next action
              </p>
              <h2 className="text-lg font-semibold">{brief.recommended_action.label}</h2>
              {brief.recommended_action.rationale && (
                <p className="text-sm text-muted-foreground">
                  {brief.recommended_action.rationale}
                </p>
              )}
              {brief.recommended_action.href && (
                <Button asChild size="sm" className="w-full">
                  <Link href={brief.recommended_action.href}>Open action</Link>
                </Button>
              )}
              {brief.watch_items.length > 0 && (
                <div className="pt-2">
                  <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">
                    Watch
                  </p>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {brief.watch_items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="mb-6 flex flex-wrap gap-3">
        <ActionLink href={`/classes/${classId}/memory`} primary>
          Update memory
        </ActionLink>
        <ActionLink href={`/classes/${classId}/plan`}>Create lesson plan</ActionLink>
        <ActionLink href={`/classes/${classId}/memory-sweep`}>Memory Sweep</ActionLink>
        <Button
          type="button"
          variant="outline"
          onClick={() => setDiscussionOpen((open) => !open)}
        >
          <MessageSquare className="mr-2 h-4 w-4" />
          Discuss class state
        </Button>
      </div>

      {discussionOpen && (
        <Card className="mb-10">
          <CardHeader>
            <CardTitle>Discuss class state</CardTitle>
            <p className="text-sm text-muted-foreground">
              Chat over the class wiki. Wiki edits stay review-only through
              memory candidates.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="max-h-80 space-y-3 overflow-y-auto rounded-md border border-border p-3">
              {discussionMessages.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Try: What should I focus on next for this class?
                </p>
              ) : (
                discussionMessages.map((message, index) => (
                  <div
                    key={`${message.role}-${index}`}
                    className={
                      message.role === "user"
                        ? "ml-auto max-w-[85%] rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
                        : "max-w-[85%] rounded-md bg-muted px-3 py-2 text-sm"
                    }
                  >
                    <p className="whitespace-pre-wrap">{message.content}</p>
                    {message.sourcePaths && message.sourcePaths.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {message.sourcePaths.slice(0, 3).map((path) => (
                          <Badge key={path} variant="outline" className="bg-background text-[10px]">
                            {path}
                          </Badge>
                        ))}
                      </div>
                    )}
                    {message.memoryCandidateCount ? (
                      <p className="mt-2 text-xs text-muted-foreground">
                        {message.memoryCandidateCount} memory{" "}
                        {message.memoryCandidateCount === 1 ? "candidate" : "candidates"} queued for review.
                      </p>
                    ) : null}
                    {message.suggestedActions && message.suggestedActions.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {message.suggestedActions.map((action) =>
                          action.href ? (
                            <Button asChild key={`${action.label}-${action.href}`} size="sm" variant="outline">
                              <Link href={action.href}>{action.label}</Link>
                            </Button>
                          ) : null,
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Textarea
                value={discussionInput}
                onChange={(event) => setDiscussionInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                    event.preventDefault();
                    void sendDiscussionMessage();
                  }
                }}
                placeholder="Ask about open loops, recent lessons, misconceptions, or what to do next..."
                className="min-h-20 flex-1"
              />
              <Button
                type="button"
                onClick={sendDiscussionMessage}
                disabled={discussionSending || discussionInput.trim().length === 0}
                className="sm:self-end"
              >
                <Send className="mr-2 h-4 w-4" />
                {discussionSending ? "Sending..." : "Send"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

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
