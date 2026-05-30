"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  client,
  uniqueWikiProposals,
  type IngestDraft,
  type WikiUpdateProposal,
} from "@/lib/api";

type CommitResult = {
  lesson_date: string;
  title: string;
  log_entry_id: string;
  applied_wiki_paths: string[];
};

function wikiProposalCategory(path: string): string {
  if (path.includes("lesson_results")) return "Lesson";
  if (path.startsWith("raw/")) return "Raw archive";
  if (path.includes("/students/")) return "Students";
  if (path.endsWith("timeline.md")) return "Timeline";
  if (
    path.includes("course_state") ||
    path.includes("misconceptions") ||
    path.includes("open_loops") ||
    path.includes("student_notes")
  ) {
    return "Roll-ups";
  }
  return "Other";
}

const CATEGORY_ORDER = ["Lesson", "Roll-ups", "Students", "Timeline", "Raw archive", "Other"];

function groupProposals(proposals: WikiUpdateProposal[]) {
  const groups = new Map<string, WikiUpdateProposal[]>();
  for (const p of uniqueWikiProposals(proposals)) {
    const cat = wikiProposalCategory(p.wiki_path);
    const list = groups.get(cat) ?? [];
    list.push(p);
    groups.set(cat, list);
  }
  return CATEGORY_ORDER.filter((k) => groups.has(k)).map((category) => ({
    category,
    items: groups.get(category)!,
  }));
}

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
  onError,
}: {
  classId: string;
  onError: (message: string | null) => void;
}) {
  const router = useRouter();
  const { artifactMarkdown: diaryMarkdown, runWithSessionRecovery } = useArtifactSession();
  const [draft, setDraft] = useState<IngestDraft | null>(null);
  const [wikiEdits, setWikiEdits] = useState<
    Record<string, { content: string; approved: boolean }>
  >({});
  const [loading, setLoading] = useState(false);
  const [showWiki, setShowWiki] = useState(false);
  const [commitResult, setCommitResult] = useState<CommitResult | null>(null);

  const grouped = useMemo(
    () => (draft ? groupProposals(draft.wiki_proposals) : []),
    [draft],
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
      setDraft(d);
      const edits: Record<string, { content: string; approved: boolean }> = {};
      for (const p of uniqueWikiProposals(d.wiki_proposals)) {
        edits[p.wiki_path] = { content: p.proposed_content, approved: true };
      }
      setWikiEdits(edits);
      setShowWiki(true);
      requestAnimationFrame(() => {
        document.getElementById("wiki-review")?.scrollIntoView({ behavior: "smooth" });
      });
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not prepare save");
    } finally {
      setLoading(false);
    }
  }, [classId, diaryMarkdown, onError, runWithSessionRecovery]);

  const commit = useCallback(async () => {
    setLoading(true);
    onError(null);
    try {
      const result = await runWithSessionRecovery((sessionId) =>
        client.ingestCommit(
          classId,
          sessionId,
          diaryMarkdown,
          Object.entries(wikiEdits).map(([wiki_path, v]) => ({
            wiki_path,
            content: v.content,
            approved: v.approved,
          })),
        ),
      );
      setCommitResult({
        lesson_date: result.lesson_date,
        title: result.title,
        log_entry_id: result.log_entry_id,
        applied_wiki_paths: result.applied_wiki_paths,
      });
      setShowWiki(false);
      router.refresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Commit failed");
    } finally {
      setLoading(false);
    }
  }, [classId, diaryMarkdown, wikiEdits, onError, router, runWithSessionRecovery]);

  const hasLessonResultsApproved = Object.entries(wikiEdits).some(
    ([path, v]) => v.approved && path.includes("lesson_results"),
  );

  return (
    <div className="space-y-8">
      <ArtifactSessionWorkspace
        thread={<IngestThread />}
        draftPanel={<DiaryDraftPanel />}
        footer={<ReadyToSaveButton onReady={handleReadyToSave} loading={loading} />}
      />

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

      {showWiki && draft && (
        <section id="wiki-review" className="scroll-mt-8 space-y-4">
          <h2 className="text-lg font-semibold">Memory files (wiki)</h2>
          <p className="text-sm text-muted-foreground">
            Uncheck any file you do not want written.{" "}
            <span className="text-foreground">lesson_results.md</span> must stay checked to save.
          </p>
          {grouped.map(({ category, items }) => (
            <div key={category} className="space-y-3">
              <h3 className="text-sm font-medium text-muted-foreground">{category}</h3>
              {items.map((p, index) => (
                <WikiProposalCard
                  key={`${p.wiki_path}::${index}`}
                  proposal={p}
                  content={wikiEdits[p.wiki_path]?.content ?? p.proposed_content}
                  approved={wikiEdits[p.wiki_path]?.approved ?? true}
                  onContentChange={(value) =>
                    setWikiEdits((prev) => ({
                      ...prev,
                      [p.wiki_path]: {
                        content: value,
                        approved: prev[p.wiki_path]?.approved ?? true,
                      },
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
            </div>
          ))}
          <Button onClick={commit} disabled={loading || !hasLessonResultsApproved}>
            {loading ? "Saving…" : "Save approved updates"}
          </Button>
          {!hasLessonResultsApproved && (
            <p className="text-xs text-destructive">
              Approve lesson_results.md to commit this lesson to memory.
            </p>
          )}
        </section>
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
