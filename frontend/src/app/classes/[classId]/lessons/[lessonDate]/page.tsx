"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { MarkdownDocumentPanel } from "@/components/klassenpilot/markdown-document-panel";
import { MarkdownPreview } from "@/components/klassenpilot/markdown-preview";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { client, type LessonDetail } from "@/lib/api";

export default function LessonDetailPage() {
  const params = useParams();
  const router = useRouter();
  const classId = params.classId as string;
  const lessonDate = params.lessonDate as string;

  const [detail, setDetail] = useState<LessonDetail | null>(null);
  const [diaryMarkdown, setDiaryMarkdown] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const d = await client.getLessonDetail(classId, lessonDate);
        if (cancelled) return;
        setDetail(d);
        setDiaryMarkdown(d.diary_markdown);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load lesson");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [classId, lessonDate]);

  const save = useCallback(async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await client.reviseLesson(classId, lessonDate, diaryMarkdown);
      setSaved(true);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [classId, lessonDate, diaryMarkdown, router]);

  if (loading) {
    return (
      <div>
        <PageHeader backHref={`/classes/${classId}`} backLabel="Class home" title="Lesson" />
        <p className="text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (!detail) {
    return (
      <div>
        <PageHeader backHref={`/classes/${classId}`} backLabel="Class home" title="Lesson" />
        {error && (
          <Alert className="border-destructive/30 bg-[var(--error-bg)] text-destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </div>
    );
  }

  const isPlanned = !detail.primary_markdown.trim();
  const memoryHref = `/classes/${classId}/memory?lessonDate=${encodeURIComponent(
    detail.date,
  )}&intent=${isPlanned ? "update_missing_results" : "correct_existing_results"}&targetKind=${
    isPlanned ? "planned_lesson" : "taught_lesson"
  }&lessonTitle=${encodeURIComponent(detail.title)}`;

  return (
    <div className="space-y-6">
      <PageHeader
        backHref={`/classes/${classId}`}
        backLabel="Class home"
        title={detail.title}
        description={isPlanned ? `Planned lesson · ${detail.date}` : `Lesson · ${detail.date}`}
      />

      {error && (
        <Alert className="border-destructive/30 bg-[var(--error-bg)] text-destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {saved && (
        <Alert className="border-border bg-muted text-foreground">
          <AlertDescription>Saved. Class memory rollups were updated from your edits.</AlertDescription>
        </Alert>
      )}

      {detail.lesson_plan_markdown && (
        <Card variant={isPlanned ? "highlight" : "default"}>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="text-base">Lesson plan</CardTitle>
                {isPlanned && (
                  <p className="text-sm text-muted-foreground">
                    Saved plan for this date. After you teach it, log what happened via Update memory.
                  </p>
                )}
              </div>
              {isPlanned && (
                <Button asChild size="sm">
                  <Link href={memoryHref}>Add lesson results</Link>
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <MarkdownPreview markdown={detail.lesson_plan_markdown} />
          </CardContent>
        </Card>
      )}

      {!isPlanned && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Lesson results</CardTitle>
            <p className="text-sm text-muted-foreground">
              Edit the diary below if something is wrong; saving updates lesson files and class rollups.
            </p>
          </CardHeader>
          <CardContent>
            <MarkdownDocumentPanel
              label="Lesson diary"
              markdown={diaryMarkdown}
              onChange={setDiaryMarkdown}
            />
            <Button className="mt-4" onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
            <Button asChild className="ml-2 mt-4" variant="outline">
              <Link href={memoryHref}>Correct with agent</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {detail.rollup_excerpts.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Memory rollups for this date</h2>
          {detail.rollup_excerpts.map((excerpt) => (
            <Card key={excerpt.wiki_path}>
              <CardHeader className="pb-2">
                <CardTitle className="font-mono text-sm font-normal text-primary">
                  {excerpt.label}
                </CardTitle>
                <p className="text-xs text-muted-foreground">{excerpt.wiki_path}</p>
              </CardHeader>
              <CardContent>
                <MarkdownPreview markdown={excerpt.markdown} />
              </CardContent>
            </Card>
          ))}
        </section>
      )}
    </div>
  );
}
