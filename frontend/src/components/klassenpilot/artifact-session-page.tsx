"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ArtifactSessionRuntimeProvider } from "@/components/assistant-ui/artifact-session-runtime";
import {
  createArtifactRuntimeConfig,
  type ArtifactMode,
} from "@/components/assistant-ui/artifact-runtime-config";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { CompletenessChecklist } from "@/lib/api";

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
  bootstrap: () => Promise<ArtifactBootstrap>;
  renderBody: (props: ArtifactSessionBodyProps) => ReactNode;
}) {
  const [data, setData] = useState<ArtifactBootstrap | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoaded(false);
    (async () => {
      try {
        const result = await bootstrap();
        if (!cancelled) setData(result);
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
    // bootstrap intentionally re-runs only on classId; it reads no other state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classId]);

  const config = useMemo(
    () =>
      data
        ? createArtifactRuntimeConfig({
            mode,
            classId,
            sessionId: data.sessionId,
            initialMarkdown: data.initialMarkdown,
            initialCompleteness: data.initialCompleteness ?? null,
          })
        : null,
    [mode, classId, data],
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
