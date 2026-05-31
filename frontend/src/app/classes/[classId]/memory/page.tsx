"use client";

import Link from "next/link";
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
import {
  FileChangeReviewPanel,
  MarkdownLineDiff,
  useFileChangeReview,
  WikiProposalEditor,
} from "@/components/klassenpilot/review";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { client, uniqueWikiProposals, type WikiUpdateProposal } from "@/lib/api";

type CommitResult = {
  lesson_date: string;
  title: string;
  log_entry_id: string;
  applied_wiki_paths: string[];
};

function ReadyToSaveButton({ onReady, loading }: { onReady: () => void; loading: boolean }) {
  const { isUpdating, readyToSave } = useArtifactSession();

  return (
    <div className="flex flex-col gap-1">
      <Button className="w-fit" onClick={onReady} disabled={loading || isUpdating}>
        {loading ? "Compiling wiki updates…" : "Ready to save memory"}
      </Button>
      {readyToSave && !loading && (
        <p className="text-xs text-primary">
          All sections filled — compile and review wiki file changes before saving.
        </p>
      )}
    </div>
  );
}

function MemoryWorkspace({
  classId,
  onError,
}: {
  classId: string;
  onError: (message: string | null) => void;
}) {
  const router = useRouter();
  const { artifactMarkdown: diaryMarkdown, runWithSessionRecovery } = useArtifactSession();
  const [proposals, setProposals] = useState<WikiUpdateProposal[]>([]);
  const [loading, setLoading] = useState(false);
  const [inReview, setInReview] = useState(false);
  const [editingWiki, setEditingWiki] = useState(false);
  const [commitResult, setCommitResult] = useState<CommitResult | null>(null);

  const {
    items: reviewItems,
    selected: selectedChange,
    selectedPath,
    setSelectedPath,
    contentByPath,
    updateContent,
    getCommitPayload,
    setApproved,
    approveAll,
    initFromProposals,
    clear: clearReview,
    hasLessonResultsApproved,
  } = useFileChangeReview(proposals);

  const selectFile = useCallback(
    (path: string) => {
      setSelectedPath(path);
      setEditingWiki(true);
    },
    [setSelectedPath],
  );

  const viewerAllHref = commitResult
    ? `/classes/${classId}/wiki/view?paths=${encodeURIComponent(commitResult.applied_wiki_paths.join(","))}`
    : "";

  const handleReadyToSave = useCallback(async () => {
    setLoading(true);
    onError(null);
    setCommitResult(null);
    try {
      await runWithSessionRecovery((sessionId) =>
        client.ingestUpdateDraft(classId, sessionId, diaryMarkdown),
      );
      const d = await runWithSessionRecovery((sessionId) =>
        client.ingestPropose(classId, sessionId),
      );
      const unique = uniqueWikiProposals(d.wiki_proposals);
      setProposals(unique);
      initFromProposals(unique);
      setInReview(true);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not prepare save");
    } finally {
      setLoading(false);
    }
  }, [classId, diaryMarkdown, onError, runWithSessionRecovery, initFromProposals]);

  const commit = useCallback(async () => {
    setLoading(true);
    onError(null);
    try {
      const result = await runWithSessionRecovery((sessionId) =>
        client.ingestCommit(classId, sessionId, diaryMarkdown, getCommitPayload()),
      );
      setCommitResult({
        lesson_date: result.lesson_date,
        title: result.title,
        log_entry_id: result.log_entry_id,
        applied_wiki_paths: result.applied_wiki_paths,
      });
      setInReview(false);
      setProposals([]);
      clearReview();
      router.refresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Commit failed");
    } finally {
      setLoading(false);
    }
  }, [classId, diaryMarkdown, getCommitPayload, clearReview, onError, router, runWithSessionRecovery]);

  const keepAll = useCallback(() => {
    approveAll();
    void commit();
  }, [approveAll, commit]);

  const undoAll = useCallback(() => {
    setInReview(false);
    setEditingWiki(false);
    setProposals([]);
    clearReview();
    onError(null);
  }, [onError, clearReview]);

  const draftPanel =
    inReview && editingWiki && selectedPath && selectedPath in contentByPath ? (
      <WikiProposalEditor
        wikiPath={selectedPath}
        markdown={contentByPath[selectedPath]}
        onChange={(value) => updateContent(selectedPath, value)}
        onBackToDiary={() => setEditingWiki(false)}
      />
    ) : (
      <DiaryDraftPanel />
    );

  return (
    <div className="space-y-8">
      <ArtifactSessionWorkspace
        thread={<IngestThread />}
        draftPanel={draftPanel}
        footer={
          !inReview ? <ReadyToSaveButton onReady={handleReadyToSave} loading={loading} /> : null
        }
        reviewDiff={
          inReview && selectedChange ? (
            <MarkdownLineDiff
              path={selectedChange.path}
              before={selectedChange.before}
              after={selectedChange.after}
              className="h-full min-h-[12rem]"
            />
          ) : null
        }
        reviewFileList={
          inReview && reviewItems.length > 0 ? (
            <FileChangeReviewPanel
              items={reviewItems}
              selectedPath={selectedPath ?? reviewItems[0]?.path ?? null}
              onSelectPath={selectFile}
              onSetApproved={setApproved}
              onUndoAll={undoAll}
              onKeepAll={keepAll}
              onSave={commit}
              saving={loading}
              saveDisabled={!hasLessonResultsApproved}
              saveLabel="Save selected files"
            />
          ) : null
        }
      />

      {inReview && !hasLessonResultsApproved && (
        <p className="text-xs text-destructive">
          Keep <span className="font-mono">lesson_results.md</span> to save this lesson to memory.
        </p>
      )}

      {commitResult && (
        <Card variant="highlight">
          <CardHeader>
            <CardTitle className="text-base">Memory saved</CardTitle>
            <p className="text-sm text-muted-foreground">
              {commitResult.title} ({commitResult.lesson_date}) — log entry{" "}
              <span className="font-mono text-xs">{commitResult.log_entry_id}</span>
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-foreground">
              {commitResult.applied_wiki_paths.length} file
              {commitResult.applied_wiki_paths.length === 1 ? "" : "s"} updated.
            </p>
            <ul className="space-y-1 text-sm">
              {commitResult.applied_wiki_paths.map((path) => (
                <li key={path}>
                  <Link
                    href={`/classes/${classId}/wiki/view?path=${encodeURIComponent(path)}`}
                    className="font-mono text-xs text-primary hover:underline"
                  >
                    {path}
                  </Link>
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-3 pt-1">
              <Button asChild>
                <Link href={viewerAllHref}>View all changes</Link>
              </Button>
              <Button variant="outline" asChild>
                <Link
                  href={
                    commitResult.lesson_date
                      ? `/classes/${classId}?highlight=${encodeURIComponent(commitResult.lesson_date)}`
                      : `/classes/${classId}`
                  }
                >
                  Back to class home
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function MemoryPage() {
  const params = useParams();
  const classId = params.classId as string;

  const bootstrap = useCallback(
    async (opts?: { preserveMarkdown?: string }) => {
      const session = await client.startIngestSession(classId);
      let draft = await client.ingestGetDraft(classId, session.session_id);
      if (opts?.preserveMarkdown) {
        draft = await client.ingestUpdateDraft(
          classId,
          session.session_id,
          opts.preserveMarkdown,
        );
      }
      return {
        sessionId: session.session_id,
        initialMarkdown: draft.diary_markdown,
        initialCompleteness: draft.completeness,
      };
    },
    [classId],
  );

  return (
    <ArtifactSessionPage
      mode="ingest"
      classId={classId}
      title="Update memory"
      description="Chat through the lesson, edit the diary on the right, then save when ready."
      bootstrap={bootstrap}
      renderBody={({ onError }: ArtifactSessionBodyProps) => (
        <MemoryWorkspace classId={classId} onError={onError} />
      )}
    />
  );
}
