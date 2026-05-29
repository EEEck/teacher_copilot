"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { useArtifactSession } from "@/components/assistant-ui/artifact-session-runtime";
import { IngestThread } from "@/components/assistant-ui/ingest-thread";
import {
  ArtifactSessionPage,
  type ArtifactSessionBodyProps,
} from "@/components/klassenpilot/artifact-session-page";
import { ArtifactSessionWorkspace } from "@/components/klassenpilot/artifact-session-workspace";
import { DiaryDraftPanel } from "@/components/klassenpilot/diary-draft-panel";
import { WikiProposalCard } from "@/components/klassenpilot/wiki-proposal-card";
import { Button } from "@/components/ui/button";
import { client, uniqueWikiProposals, type IngestDraft } from "@/lib/api";

function ReadyToSaveButton({ onReady, loading }: { onReady: () => void; loading: boolean }) {
  const { isUpdating, readyToSave } = useArtifactSession();

  return (
    <div className="flex flex-col gap-1">
      <Button className="w-fit" onClick={onReady} disabled={loading || isUpdating}>
        Ready to save memory
      </Button>
      {readyToSave && (
        <p className="text-xs text-primary">
          All sections filled — review wiki updates below before saving.
        </p>
      )}
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
  const { artifactMarkdown: diaryMarkdown } = useArtifactSession();
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
      for (const p of uniqueWikiProposals(d.wiki_proposals)) {
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
      <ArtifactSessionWorkspace
        thread={<IngestThread />}
        draftPanel={<DiaryDraftPanel />}
        footer={<ReadyToSaveButton onReady={handleReadyToSave} loading={loading} />}
      />

      {showWiki && draft && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Memory files (wiki)</h2>
          <p className="text-sm text-muted-foreground">
            Review proposed wiki updates before committing.
          </p>
          {uniqueWikiProposals(draft.wiki_proposals).map((p, index) => (
            <WikiProposalCard
              key={`${p.wiki_path}::${index}`}
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

export default function MemoryPage() {
  const params = useParams();
  const classId = params.classId as string;
  const router = useRouter();

  const bootstrap = useCallback(async () => {
    const session = await client.startIngestSession(classId);
    const draft = await client.ingestGetDraft(classId, session.session_id);
    return {
      sessionId: session.session_id,
      initialMarkdown: draft.diary_markdown,
      initialCompleteness: draft.completeness,
    };
  }, [classId]);

  return (
    <ArtifactSessionPage
      mode="ingest"
      classId={classId}
      title="Update memory"
      description="Chat through the lesson, edit the diary on the right, then save when ready."
      bootstrap={bootstrap}
      renderBody={({ sessionId, onError }: ArtifactSessionBodyProps) => (
        <MemoryWorkspace
          classId={classId}
          sessionId={sessionId}
          onError={onError}
          onDone={(lessonDate) => {
            router.push(
              lessonDate
                ? `/classes/${classId}?highlight=${encodeURIComponent(lessonDate)}`
                : `/classes/${classId}`,
            );
            router.refresh();
          }}
        />
      )}
    />
  );
}
