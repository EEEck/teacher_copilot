"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { Maximize2Icon, MinusIcon, XIcon } from "lucide-react";

import { createArtifactRuntimeConfig } from "@/components/assistant-ui/artifact-runtime-config";
import { ArtifactSessionRuntimeProvider } from "@/components/assistant-ui/artifact-session-runtime";
import { DiscussThread } from "@/components/assistant-ui/discuss-thread";
import { AgentMark, EEEck } from "@/components/klassenpilot/agent-mark";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { client, type ChatMessage } from "@/lib/api";
import { toWorkflowDraftSnapshot } from "@/features/workflow-drafts/workflow-draft-bootstrap";
import { workflowDraftRuntimeKey } from "@/features/workflow-drafts/workflow-draft-runtime-key";
import { useWorkflowDraftStore } from "@/features/workflow-drafts/workflow-draft-store";
import { cn } from "@/lib/utils";

/** Discuss FAB — a step above the size-12 ? button. */
const FAB_BOX_PX = 76;
const HEADER_BOX_PX = 28;

export type DiscussDockState = "closed" | "minimized" | "expanded";

type DiscussDockProps = {
  classId: string;
  state: DiscussDockState;
  onStateChange: (state: DiscussDockState) => void;
};

type BootstrapState = {
  sessionId: string;
  draftId: string;
  artifactRevision: number;
  artifactHash: string;
  turnInProgress: boolean;
  latestTurnComplete: boolean;
  initialMessages: ChatMessage[];
};

const DEFAULT_WIDTH_PX = Math.round(26 * 16 * 1.2); // ~20% wider than prior 26rem
const MIN_WIDTH_PX = 320;
const MAX_WIDTH_VW = 0.92;

/**
 * Gmail-style docked helper on class home.
 * Chat stack is imported (runtime config + provider + DiscussThread);
 * this file owns window chrome, width, and a fixed-height shell Thread needs.
 */
export function DiscussDock({ classId, state, onStateChange }: DiscussDockProps) {
  const upsert = useWorkflowDraftStore((s) => s.upsert);
  const draftsById = useWorkflowDraftStore((s) => s.draftsById);
  const [boot, setBoot] = useState<BootstrapState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [widthPx, setWidthPx] = useState(DEFAULT_WIDTH_PX);
  const inflightRef = useRef<Promise<void> | null>(null);
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);

  const clampWidth = useCallback((next: number) => {
    const max = Math.floor(window.innerWidth * MAX_WIDTH_VW);
    return Math.min(max, Math.max(MIN_WIDTH_PX, next));
  }, []);

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      // Dragging the left edge: move left ⇒ wider.
      const delta = drag.startX - event.clientX;
      setWidthPx(clampWidth(drag.startWidth + delta));
    };
    const onUp = () => {
      dragRef.current = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [clampWidth]);

  const onResizePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragRef.current = { startX: event.clientX, startWidth: widthPx };
    document.body.style.cursor = "ew-resize";
    document.body.style.userSelect = "none";
  };

  const bootstrap = useCallback(async () => {
    if (inflightRef.current) {
      await inflightRef.current;
      return;
    }
    // Prefer an in-memory discuss draft for this class so leave/return keeps
    // the same draftId (and rich thread overlay) while open-or-resume loads.
    const cached = Object.values(
      useWorkflowDraftStore.getState().draftsById,
    ).find((d) => d.mode === "discuss" && d.classId === classId);
    if (cached) {
      setBoot({
        sessionId: cached.sessionId,
        draftId: cached.draftId,
        artifactRevision: cached.artifactRevision,
        artifactHash: cached.artifactHash,
        turnInProgress: cached.turnInProgress,
        latestTurnComplete: cached.latestTurnComplete,
        initialMessages: cached.messages,
      });
    }
    setLoading(true);
    setError(null);
    const run = (async () => {
      try {
        // Backend open_draft resumes the active discuss session for this class.
        const session = await client.startDiscussionSession(classId);
        const draft = await client.discussionGetDraft(classId, session.session_id);
        const snapshot = toWorkflowDraftSnapshot("discuss", classId, {
          sessionId: session.session_id,
          draftId: draft.draft_id || session.draft_id,
          artifactRevision: draft.artifact_revision || session.artifact_revision,
          artifactHash: draft.artifact_hash || session.artifact_hash,
          turnInProgress: draft.turn_in_progress ?? session.turn_in_progress,
          latestTurnComplete:
            draft.latest_turn_complete ?? session.latest_turn_complete,
          initialMessages: draft.messages?.length
            ? draft.messages
            : session.messages,
          initialMarkdown: "",
        });
        if (!snapshot) {
          throw new Error("Discussion draft missing id");
        }
        upsert(snapshot);
        setBoot({
          sessionId: session.session_id,
          draftId: snapshot.draftId,
          artifactRevision: snapshot.artifactRevision,
          artifactHash: snapshot.artifactHash,
          turnInProgress: snapshot.turnInProgress,
          latestTurnComplete: snapshot.latestTurnComplete,
          initialMessages: snapshot.messages,
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to start discussion");
        if (!cached) setBoot(null);
      } finally {
        setLoading(false);
      }
    })();
    inflightRef.current = run.finally(() => {
      inflightRef.current = null;
    });
    await inflightRef.current;
  }, [classId, upsert]);

  useEffect(() => {
    if (state === "closed") {
      setBoot(null);
      setError(null);
      setLoading(false);
      return;
    }
    if (!boot && !loading && !error) {
      void bootstrap();
    }
  }, [state, boot, loading, error, bootstrap]);

  const showFab = state === "closed";
  const minimized = state === "minimized";
  const turnInProgress = boot
    ? Boolean(draftsById[boot.draftId]?.turnInProgress ?? boot.turnInProgress)
    : false;
  const headerMood = minimized ? "sleeping" : turnInProgress ? "thinking" : "default";

  const sessionChat =
    boot != null && state !== "closed" ? (
      <ArtifactSessionRuntimeProvider
        key={workflowDraftRuntimeKey(boot.draftId, boot.sessionId)}
        config={createArtifactRuntimeConfig({
          mode: "discuss",
          classId,
          sessionId: boot.sessionId,
          draftId: boot.draftId,
          artifactRevision: boot.artifactRevision,
          artifactHash: boot.artifactHash,
          turnInProgress: boot.turnInProgress,
          latestTurnComplete: boot.latestTurnComplete,
          initialMessages: boot.initialMessages,
          initialMarkdown: "",
        })}
      >
        <DiscussThread />
      </ArtifactSessionRuntimeProvider>
    ) : null;

  return (
    <>
      {showFab ? (
        <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2">
          <button
            type="button"
            aria-label="Open discuss with EEEck"
            onClick={() => onStateChange("expanded")}
            className={cn(
              "relative flex items-center justify-center overflow-visible rounded-full",
              "focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
            )}
            style={{ width: FAB_BOX_PX, height: FAB_BOX_PX }}
          >
            <EEEck boxSize={FAB_BOX_PX} />
          </button>
          <button
            type="button"
            aria-label="Discuss class state"
            onClick={() => onStateChange("expanded")}
            className={cn(
              "flex size-12 items-center justify-center rounded-full",
              "bg-primary text-3xl font-semibold leading-none text-primary-foreground shadow-sm",
              "hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
            )}
          >
            ?
          </button>
        </div>
      ) : null}

      {state !== "closed" ? (
        <div
          className={cn(
            // Viewport-pinned (Gmail-style). Do NOT add `relative` here — it
            // can override `fixed` in the Tailwind cascade and wire the panel
            // into page scroll (minimized looked correct; expanded did not).
            "fixed bottom-4 right-4 z-50 flex flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm",
            minimized ? "h-auto" : "h-[min(36rem,calc(100vh-6rem))]",
          )}
          style={{ width: minimized ? Math.min(widthPx, 360) : widthPx }}
        >
          {!minimized ? (
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize discussion panel"
              onPointerDown={onResizePointerDown}
              className="absolute inset-y-0 left-0 z-10 w-1.5 cursor-ew-resize hover:bg-primary/20"
            />
          ) : null}
          <DockHeader
            title="Discuss class state"
            minimized={minimized}
            mood={headerMood}
            onExpand={() => onStateChange("expanded")}
            onMinimize={() => onStateChange("minimized")}
            onClose={() => onStateChange("closed")}
          />
          <div
            className={cn(
              "flex min-h-0 flex-col overflow-hidden",
              minimized ? "hidden" : "min-h-0 flex-1",
            )}
          >
            {loading && !boot ? (
              <p className="p-4 text-sm text-muted-foreground">
                Starting discussion…
              </p>
            ) : null}
            {error ? (
              <div className="p-3">
                <Alert className="border-destructive/30 bg-[var(--error-bg)] text-destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={() => {
                    setError(null);
                    void bootstrap();
                  }}
                >
                  Retry
                </Button>
              </div>
            ) : null}
            {sessionChat ? (
              <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
                {sessionChat}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  );
}

function DockHeader({
  title,
  minimized,
  mood,
  onExpand,
  onMinimize,
  onClose,
}: {
  title: string;
  minimized?: boolean;
  mood: "default" | "sleeping" | "thinking";
  onExpand: () => void;
  onMinimize: () => void;
  onClose: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center gap-1 border-b border-border bg-muted px-2 py-1.5">
      <AgentMark
        boxSize={HEADER_BOX_PX}
        mood={mood}
        title="EEEck"
        className="shrink-0"
      />
      <button
        type="button"
        className="min-w-0 flex-1 truncate px-1 text-left text-sm font-medium text-foreground"
        onClick={minimized ? onExpand : undefined}
      >
        {title}
      </button>
      {minimized ? (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          aria-label="Expand discussion"
          onClick={onExpand}
        >
          <Maximize2Icon className="size-3.5" />
        </Button>
      ) : (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          aria-label="Minimize discussion"
          onClick={onMinimize}
        >
          <MinusIcon className="size-3.5" />
        </Button>
      )}
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="size-7"
        aria-label="Close discussion"
        onClick={onClose}
      >
        <XIcon className="size-3.5" />
      </Button>
    </div>
  );
}
