"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ArtifactSessionRuntimeProvider } from "@/components/assistant-ui/artifact-session-runtime";
import {
  createArtifactRuntimeConfig,
  type ArtifactMode,
} from "@/components/assistant-ui/artifact-runtime-config";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { ChatMessage, CompletenessChecklist } from "@/lib/api";
import { toWorkflowDraftSnapshot } from "@/features/workflow-drafts/workflow-draft-bootstrap";
import { workflowDraftRuntimeKey } from "@/features/workflow-drafts/workflow-draft-runtime-key";
import { useWorkflowDraftStore } from "@/features/workflow-drafts/workflow-draft-store";

export type ArtifactBootstrapOptions = {
  /** Re-apply draft after the server lost the in-memory session (e.g. backend restart). */
  preserveMarkdown?: string;
};

export type ArtifactBootstrap = {
  sessionId: string;
  draftId?: string;
  artifactRevision?: number;
  artifactHash?: string;
  turnInProgress?: boolean;
  latestTurnComplete?: boolean;
  initialMessages?: ChatMessage[];
  initialMarkdown: string;
  initialCompleteness?: CompletenessChecklist | null;
  initialMemoryState?: Record<string, unknown> | null;
  openingMessage?: string;
};

export type ArtifactSessionBodyProps = {
  sessionId: string;
  openingMessage: string;
  onError: (message: string | null) => void;
};

/**
 * Shared shell for every artifact-session route (update memory, plan lesson, …).
 * Owns session bootstrap, the loaded/error gate, header, and the runtime
 * provider. Mode-specific UI (thread, draft panel, footer, wiki review) is
 * supplied via `renderBody`. Adding a mode = a new thin wrapper, not a new page.
 */
export function ArtifactSessionPage({
  mode,
  classId,
  title,
  description,
  bootstrap,
  lessonDate,
  lessonTitle,
  renderBody,
}: {
  mode: ArtifactMode;
  classId: string;
  title: string;
  description?: string;
  bootstrap: (opts?: ArtifactBootstrapOptions) => Promise<ArtifactBootstrap>;
  lessonDate?: string;
  lessonTitle?: string;
  renderBody: (props: ArtifactSessionBodyProps) => ReactNode;
}) {
  const [data, setData] = useState<ArtifactBootstrap | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);
  const sessionIdRef = useRef("");
  const inflightBootstrapRef = useRef<{
    fn: unknown;
    promise: Promise<unknown>;
  } | null>(null);

  const loadBootstrap = useCallback(
    async (opts?: ArtifactBootstrapOptions) => {
      const result = await bootstrap(opts);
      sessionIdRef.current = result.sessionId;
      const snapshot = toWorkflowDraftSnapshot(mode, classId, result);
      if (snapshot) useWorkflowDraftStore.getState().upsert(snapshot);
      setData(result);
      return result;
    },
    [bootstrap, classId, mode],
  );

  const onSessionLost = useCallback(
    async (preserveMarkdown: string) => {
      await loadBootstrap({ preserveMarkdown });
      setSessionNotice(
        "Server session was reset. Your draft and saved chat state were restored.",
      );
    },
    [loadBootstrap],
  );

  useEffect(() => {
    let cancelled = false;
    setLoaded(false);
    setSessionNotice(null);
    (async () => {
      try {
        // React StrictMode runs this effect twice in dev; reuse the in-flight
        // bootstrap so each page open creates exactly one backend session
        // (a second POST would leave a ghost session in beta telemetry).
        let entry = inflightBootstrapRef.current;
        if (!entry || entry.fn !== loadBootstrap) {
          const promise = loadBootstrap().finally(() => {
            if (inflightBootstrapRef.current?.promise === promise) {
              inflightBootstrapRef.current = null;
            }
          });
          entry = { fn: loadBootstrap, promise };
          inflightBootstrapRef.current = entry;
        }
        await entry.promise;
        if (!cancelled) setError(null);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to start session");
        }
      } finally {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [classId, loadBootstrap]);

  const config = useMemo(
    () =>
      data
        ? createArtifactRuntimeConfig({
            mode,
            classId,
            sessionId: data.sessionId,
            draftId: data.draftId,
            artifactRevision: data.artifactRevision,
            artifactHash: data.artifactHash,
            turnInProgress: data.turnInProgress,
            latestTurnComplete: data.latestTurnComplete,
            lessonDate,
            lessonTitle,
            initialMessages: data.initialMessages,
            getSessionId: () => sessionIdRef.current,
            onSessionLost,
            initialMarkdown: data.initialMarkdown,
            initialCompleteness: data.initialCompleteness ?? null,
            initialMemoryState: data.initialMemoryState ?? null,
          })
        : null,
    [mode, classId, data, lessonDate, lessonTitle, onSessionLost],
  );

  const header = (
    <PageHeader
      backHref={`/classes/${classId}`}
      backLabel="Class home"
      title={title}
      description={description}
    />
  );

  // Gate on an explicit loaded flag — an empty markdown draft is valid and must
  // not leave the page stuck on "Starting session…" (the old `!draft` bug).
  if (!loaded || !data || !config) {
    return (
      <div>
        {header}
        {error ? (
          <Alert className="mb-6 border-destructive/30 bg-[var(--error-bg)] text-destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : (
          <p className="text-muted-foreground">Starting session…</p>
        )}
      </div>
    );
  }

  return (
    <div>
      {header}
      {sessionNotice && (
        <Alert className="mb-6 border-border bg-muted text-foreground">
          <AlertDescription>{sessionNotice}</AlertDescription>
        </Alert>
      )}
      {error && (
        <Alert className="mb-6 border-destructive/30 bg-[var(--error-bg)] text-destructive">
          <AlertDescription className="whitespace-pre-line">{error}</AlertDescription>
        </Alert>
      )}
      {data.latestTurnComplete === false && data.turnInProgress !== true && (
        <Alert className="mb-6 border-destructive/30 bg-[var(--error-bg)] text-destructive">
          <AlertDescription>
            The previous chat turn was interrupted before it reached the draft. Send
            that note again, or discard the draft to start cleanly.
          </AlertDescription>
        </Alert>
      )}
      <ArtifactSessionRuntimeProvider
        key={workflowDraftRuntimeKey(data.draftId, data.sessionId)}
        config={config}
      >
        {renderBody({
          sessionId: data.sessionId,
          openingMessage: data.openingMessage ?? "",
          onError: setError,
        })}
      </ArtifactSessionRuntimeProvider>
    </div>
  );
}
