"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { IngestThread } from "@/components/assistant-ui/ingest-thread";
import {
  IngestRuntimeProvider,
  useIngestRuntime,
} from "@/components/assistant-ui/ingest-runtime-provider";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/assistant-ui/resizable";
import { DiaryDraftPanel } from "@/components/klassenpilot/diary-draft-panel";
import { WikiProposalCard } from "@/components/klassenpilot/wiki-proposal-card";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  client,
  type CompletenessChecklist,
  type IngestDraft,
  type IngestSession,
} from "@/lib/api";

function ReadyToSaveButton({
  onReady,
  loading,
}: {
  onReady: () => void;
  loading: boolean;
}) {
  const { isUpdating, readyToPropose } = useIngestRuntime();

  return (
    <div className="flex flex-col gap-1">
      <Button className="w-fit" onClick={onReady} disabled={loading || isUpdating}>
        Ready to save memory
      </Button>
      {readyToPropose && (
        <p className="text-xs text-primary">
          All sections filled — review wiki updates below before saving.
        </p>
      )}
    </div>
  );
}

export default function MemoryPage() {
  const params = useParams();
  const classId = params.classId as string;
  const router = useRouter();

  const [session, setSession] = useState<IngestSession | null>(null);
  const [initialDiary, setInitialDiary] = useState<string>("");
  const [checklist, setChecklist] = useState<CompletenessChecklist | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await client.startIngestSession(classId);
        if (cancelled) return;
        setSession(s);
        setChecklist(s.completeness);
        const d = await client.ingestGetDraft(classId, s.session_id);
        if (cancelled) return;
        setInitialDiary(d.diary_markdown);
        setChecklist(d.completeness);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to start session");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [classId]);

  const onCompletenessChange = useCallback((c: CompletenessChecklist) => {
    setChecklist(c);
  }, []);

  if (!session || !initialDiary) {
    return (
      <div>
        <PageHeader backHref={`/classes/${classId}`} backLabel="Class home" title="Update memory" />
        <p className="text-muted-foreground">Starting session…</p>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        backHref={`/classes/${classId}`}
        backLabel="Class home"
        title="Update memory"
        description="Chat through the lesson, edit the diary on the right, then save when ready."
      />

      {error && (
        <Alert className="mb-6 border-destructive/30 bg-[var(--error-bg)] text-destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <IngestRuntimeProvider
        classId={classId}
        sessionId={session.session_id}
        initialDiaryMarkdown={initialDiary}
        initialCompleteness={checklist}
        onCompletenessChange={onCompletenessChange}
      >
        <MemoryWorkspace
          classId={classId}
          sessionId={session.session_id}
          onError={setError}
          onDone={(lessonDate) => {
            router.push(
              lessonDate
                ? `/classes/${classId}?highlight=${encodeURIComponent(lessonDate)}`
                : `/classes/${classId}`,
            );
            router.refresh();
          }}
        />
      </IngestRuntimeProvider>
    </div>
  );
}

function MemoryWorkspace({
  classId,
  sessionId,
  onError,
  onDone,
}: {
  classId: string;
  sessionId: string;
  onError: (message: string | null) => void;
  onDone: (lessonDate?: string) => void;
}) {
  const { diaryMarkdown } = useIngestRuntime();
  const [draft, setDraft] = useState<IngestDraft | null>(null);
  const [wikiEdits, setWikiEdits] = useState<
    Record<string, { content: string; approved: boolean }>
  >({});
  const [loading, setLoading] = useState(false);
  const [showWiki, setShowWiki] = useState(false);

  const handleReadyToSave = useCallback(async () => {
    setLoading(true);
    onError(null);
    try {
      await client.ingestUpdateDraft(classId, sessionId, diaryMarkdown);
      const d = await client.ingestPropose(classId, sessionId);
      setDraft(d);
      const edits: Record<string, { content: string; approved: boolean }> = {};
      for (const p of d.wiki_proposals) {
        edits[p.wiki_path] = { content: p.proposed_content, approved: true };
      }
      setWikiEdits(edits);
      setShowWiki(true);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not prepare save");
    } finally {
      setLoading(false);
    }
  }, [classId, sessionId, diaryMarkdown, onError]);

  const commit = useCallback(async () => {
    setLoading(true);
    onError(null);
    try {
      const result = await client.ingestCommit(
        classId,
        sessionId,
        diaryMarkdown,
        Object.entries(wikiEdits).map(([wiki_path, v]) => ({
          wiki_path,
          content: v.content,
          approved: v.approved,
        })),
      );
      onDone(result.lesson_date || undefined);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Commit failed");
    } finally {
      setLoading(false);
    }
  }, [classId, sessionId, diaryMarkdown, wikiEdits, onError, onDone]);

  return (
    <div className="space-y-8">
      <ResizablePanelGroup orientation="horizontal" className="min-h-[560px] rounded-lg border">
        <ResizablePanel defaultSize={58} minSize={40}>
          <div className="flex h-full flex-col gap-3 p-4">
            <Card className="min-h-0 flex-1 overflow-hidden">
              <CardContent className="flex h-full min-h-[480px] flex-col p-0">
                <IngestThread />
              </CardContent>
            </Card>
            <ReadyToSaveButton onReady={handleReadyToSave} loading={loading} />
          </div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={42} minSize={30}>
          <div className="h-full p-4">
            <DiaryDraftPanel />
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>

      {showWiki && draft && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Memory files (wiki)</h2>
          <p className="text-sm text-muted-foreground">
            Review proposed wiki updates before committing.
          </p>
          {draft.wiki_proposals.map((p) => (
            <WikiProposalCard
              key={p.wiki_path}
              proposal={p}
              content={wikiEdits[p.wiki_path]?.content ?? p.proposed_content}
              approved={wikiEdits[p.wiki_path]?.approved ?? true}
              onContentChange={(value) =>
                setWikiEdits((prev) => ({
                  ...prev,
                  [p.wiki_path]: { content: value, approved: prev[p.wiki_path]?.approved ?? true },
                }))
              }
              onApprovedChange={(value) =>
                setWikiEdits((prev) => ({
                  ...prev,
                  [p.wiki_path]: {
                    content: prev[p.wiki_path]?.content ?? p.proposed_content,
                    approved: value,
                  },
                }))
              }
            />
          ))}
          <Button onClick={commit} disabled={loading}>
            Save approved updates
          </Button>
        </section>
      )}
    </div>
  );
}
