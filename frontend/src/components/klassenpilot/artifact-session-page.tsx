"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ArtifactSessionRuntimeProvider } from "@/components/assistant-ui/artifact-session-runtime";
import {
  createArtifactRuntimeConfig,
  type ArtifactMode,
} from "@/components/assistant-ui/artifact-runtime-config";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { CompletenessChecklist } from "@/lib/api";

export type ArtifactBootstrapOptions = {
  /** Re-apply draft after the server lost the in-memory session (e.g. backend restart). */
  preserveMarkdown?: string;
};

export type ArtifactBootstrap = {
  sessionId: string;
  initialMarkdown: string;
  initialCompleteness?: CompletenessChecklist | null;
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
  renderBody,
}: {
  mode: ArtifactMode;
  classId: string;
  title: string;
  description?: string;
  bootstrap: (opts?: ArtifactBootstrapOptions) => Promise<ArtifactBootstrap>;
  renderBody: (props: ArtifactSessionBodyProps) => ReactNode;
}) {
  const [data, setData] = useState<ArtifactBootstrap | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);
  const sessionIdRef = useRef("");

  const loadBootstrap = useCallback(
    async (opts?: ArtifactBootstrapOptions) => {
      const result = await bootstrap(opts);
      sessionIdRef.current = result.sessionId;
      setData(result);
      return result;
    },
    [bootstrap],
  );

  const onSessionLost = useCallback(
    async (preserveMarkdown: string) => {
      await loadBootstrap({ preserveMarkdown });
      setSessionNotice(
        "Server session was reset (e.g. after a restart). Your draft was restored — chat history from this tab was cleared.",
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
        await loadBootstrap();
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
            getSessionId: () => sessionIdRef.current,
            onSessionLost,
            initialMarkdown: data.initialMarkdown,
            initialCompleteness: data.initialCompleteness ?? null,
          })
        : null,
    [mode, classId, data, onSessionLost],
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
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <ArtifactSessionRuntimeProvider config={config}>
        {renderBody({
          sessionId: data.sessionId,
          openingMessage: data.openingMessage ?? "",
          onError: setError,
        })}
      </ArtifactSessionRuntimeProvider>
    </div>
  );
}
