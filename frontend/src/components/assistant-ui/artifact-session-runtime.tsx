"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  AssistantRuntimeProvider,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import { isUnknownSessionError, type ChatMessage, type CompletenessChecklist } from "@/lib/api";
import type { MemoryCandidate } from "@/lib/api";
import type { ChatStreamChunk } from "@/components/assistant-ui/artifact-runtime-config";
import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";
import { initialAssistantRunContent, lessonContextFromMemoryState } from "@/lib/chat-run-feedback";
import { extractSessionAttachments, type SessionAttachment } from "@/lib/session-attachments";
import { cancelTurn, runTurn } from "@/features/workflow-drafts/turn-runner";
import { useWorkflowChatRuntime, type UpdateWorkflowThread } from "@/features/workflow-drafts/workflow-chat-runtime";
import { workflowTurnActivity } from "@/features/workflow-drafts/workflow-turn-activity";
import { useWorkflowDraftStore } from "@/features/workflow-drafts/workflow-draft-store";

export type ArtifactChatResult = {
  reply: string;
  artifactMarkdown: string;
  draftId?: string;
  artifactRevision?: number;
  artifactHash?: string;
  completeness?: CompletenessChecklist | null;
  readyToSave?: boolean;
  lastChangeSummary?: string | null;
  memoryCandidates?: MemoryCandidate[];
  memoryState?: Record<string, unknown> | null;
};

export type ArtifactSessionConfig = {
  mode: ArtifactMode;
  classId: string;
  sessionId: string;
  draftId?: string;
  artifactRevision?: number;
  artifactHash?: string;
  turnInProgress?: boolean;
  latestTurnComplete?: boolean;
  /** Plan-page lesson date used for pending-turn labels when memory state has none. */
  lessonDate?: string;
  lessonTitle?: string;
  initialMarkdown: string;
  initialMessages?: ChatMessage[];
  initialCompleteness?: CompletenessChecklist | null;
  initialMemoryState?: Record<string, unknown> | null;
  chatStream: (args: {
    message: string;
    currentMarkdown: string;
    attachments?: SessionAttachment[];
    signal?: AbortSignal;
  }) => AsyncGenerator<ChatStreamChunk>;
  patchDraft?: (markdown: string) => Promise<{
    completeness?: CompletenessChecklist;
    readyToSave?: boolean;
    draftId?: string;
    artifactRevision?: number;
    artifactHash?: string;
  }>;
  getSessionId?: () => string;
  onSessionLost?: (preserveMarkdown: string) => Promise<void>;
  onCompletenessChange?: (checklist: CompletenessChecklist) => void;
};

type ArtifactSessionContextValue = {
  classId: string;
  sessionId: string;
  draftId: string;
  artifactRevision: number;
  artifactHash: string;
  turnInProgress: boolean;
  latestTurnComplete: boolean;
  /** Retries once after re-creating the server session when the backend was restarted. */
  runWithSessionRecovery: <T>(
    run: (sessionId: string) => Promise<T>,
    preserveMarkdown?: string,
  ) => Promise<T>;
  artifactMarkdown: string;
  setArtifactMarkdown: (value: string, source?: "manual" | "agent") => void;
  completeness: CompletenessChecklist | null;
  readyToSave: boolean;
  lastChangeSummary: string | null;
  memoryState: Record<string, unknown> | null;
  memoryCandidates: MemoryCandidate[];
  isUpdating: boolean;
  syncStatus: "idle" | "saving" | "error";
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
};

const ArtifactSessionContext = createContext<ArtifactSessionContextValue | null>(null);

export function useArtifactSession() {
  const ctx = useContext(ArtifactSessionContext);
  if (!ctx) throw new Error("useArtifactSession must be used within ArtifactSessionRuntimeProvider");
  return ctx;
}

function extractText(message: AppendMessage): string {
  const content = Array.isArray(message.content) ? message.content : [];
  return content
    .filter((part): part is { type: "text"; text: string } => part.type === "text")
    .map((part) => part.text)
    .join("\n");
}

type EditorState = { history: string[]; index: number };

/**
 * Chat/session provider for artifact workflows (plan / ingest / discuss).
 *
 * Runner-lite (docs/beta_readiness_audit_2026-07-13.md §A.1): the SSE turn is
 * owned by the module-level turn runner and the workflow draft store — this
 * component only renders store state, dispatches user intent (send / stop /
 * edit), and owns the page-local artifact editor. Navigation never touches a
 * running turn; only the Stop button aborts the client stream.
 */
export function ArtifactSessionRuntimeProvider({
  config,
  children,
}: {
  config: ArtifactSessionConfig;
  children: ReactNode;
}) {
  const {
    classId,
    mode,
    sessionId,
    draftId = "",
    artifactRevision = 0,
    artifactHash = "",
    turnInProgress = false,
    latestTurnComplete = true,
    lessonDate: configLessonDate = "",
    lessonTitle: configLessonTitle = "",
    initialMarkdown,
    initialCompleteness = null,
    initialMemoryState = null,
    chatStream,
    patchDraft,
    getSessionId: configGetSessionId,
    onSessionLost,
    onCompletenessChange,
  } = config;

  // Store key for this mount; the provider remounts (workflowDraftRuntimeKey)
  // when the draft/session identity changes.
  const draftKey = draftId || sessionId;

  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = configGetSessionId?.() ?? sessionId;
  const [recoveredSessionId, setRecoveredSessionId] = useState(
    configGetSessionId?.() ?? sessionId,
  );

  const storedDraft = useWorkflowDraftStore((state) => state.draftsById[draftKey]);
  const turn = useWorkflowDraftStore((state) => state.turnByDraftId[draftKey]);

  const configLessonDateRef = useRef(configLessonDate);
  configLessonDateRef.current = configLessonDate;
  const configLessonTitleRef = useRef(configLessonTitle);
  configLessonTitleRef.current = configLessonTitle;

  const [editor, setEditor] = useState<EditorState>({
    history: [initialMarkdown],
    index: 0,
  });
  const [syncStatus, setSyncStatus] = useState<"idle" | "saving" | "error">("idle");

  const artifactMarkdown = editor.history[editor.index] ?? initialMarkdown;
  const editorRef = useRef(editor);
  editorRef.current = editor;
  const skipPatchRef = useRef(true);
  const lastSyncedRef = useRef(initialMarkdown);
  const patchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pushMarkdown = useCallback((markdown: string, source: "manual" | "agent") => {
    if (source === "agent") {
      skipPatchRef.current = true;
      lastSyncedRef.current = markdown;
    }
    setEditor((state) => {
      const base = state.history.slice(0, state.index + 1);
      if (base[base.length - 1] === markdown) return state;
      return { history: [...base, markdown], index: base.length };
    });
  }, []);

  // Re-bootstrap without remount (ArtifactSessionPage refresh path).
  useEffect(() => {
    if (initialMarkdown === lastSyncedRef.current) return;
    pushMarkdown(initialMarkdown, "agent");
  }, [artifactRevision, artifactHash, initialMarkdown, pushMarkdown]);

  // Agent-side artifact updates (turn completion, notifier/recovery upserts)
  // flow store → editor; teacher edits flow editor → PATCH → store.
  useEffect(() => {
    if (!storedDraft) return;
    if (storedDraft.artifactMarkdown !== lastSyncedRef.current) {
      pushMarkdown(storedDraft.artifactMarkdown, "agent");
    }
  }, [storedDraft, pushMarkdown]);

  const lastNotifiedCompletenessRef = useRef<CompletenessChecklist | null>(null);
  useEffect(() => {
    const checklist = storedDraft?.completeness ?? null;
    if (!checklist || checklist === lastNotifiedCompletenessRef.current) return;
    lastNotifiedCompletenessRef.current = checklist;
    onCompletenessChange?.(checklist);
  }, [storedDraft?.completeness, onCompletenessChange]);

  const setArtifactMarkdown = useCallback(
    (value: string, source: "manual" | "agent" = "manual") => {
      pushMarkdown(value, source);
    },
    [pushMarkdown],
  );

  const undo = useCallback(() => {
    skipPatchRef.current = false;
    setEditor((state) => ({ ...state, index: Math.max(0, state.index - 1) }));
  }, []);

  const redo = useCallback(() => {
    skipPatchRef.current = false;
    setEditor((state) => ({
      ...state,
      index: Math.min(state.history.length - 1, state.index + 1),
    }));
  }, []);

  // Tell the app-wide notifier which chat is on screen, so it doesn't toast a
  // completion the teacher is already watching.
  useEffect(() => {
    useWorkflowDraftStore.getState().setMountedDraftId(draftKey);
    return () => {
      const store = useWorkflowDraftStore.getState();
      if (store.mountedDraftId === draftKey) store.setMountedDraftId(null);
    };
  }, [draftKey]);

  const runWithSessionRecovery = useCallback(
    async <T,>(run: (sessionId: string) => Promise<T>, preserveMarkdown?: string): Promise<T> => {
      const markdown =
        preserveMarkdown ??
        editorRef.current.history[editorRef.current.index] ??
        initialMarkdown;
      try {
        return await run(sessionIdRef.current);
      } catch (err) {
        if (!onSessionLost || !isUnknownSessionError(err)) throw err;
        await onSessionLost(markdown);
        sessionIdRef.current = configGetSessionId?.() ?? sessionIdRef.current;
        setRecoveredSessionId(sessionIdRef.current);
        return await run(sessionIdRef.current);
      }
    },
    [initialMarkdown, onSessionLost, configGetSessionId],
  );

  const onNew = useCallback(
    async (message: AppendMessage, _updateThread: UpdateWorkflowThread) => {
      if (message.role !== "user") return;
      const text = extractText(message);
      const attachments = await extractSessionAttachments(
        message as unknown as Parameters<typeof extractSessionAttachments>[0],
      );
      const currentMarkdown =
        editorRef.current.history[editorRef.current.index] ?? initialMarkdown;

      const snapshot = useWorkflowDraftStore.getState().draftsById[draftKey];
      const fromMemory = lessonContextFromMemoryState(snapshot?.memoryState ?? null);
      const lessonDate =
        fromMemory.lessonDate || configLessonDateRef.current.trim() || undefined;
      const lessonTitle =
        fromMemory.lessonTitle || configLessonTitleRef.current.trim() || undefined;

      await runTurn({
        draftId: draftKey,
        mode,
        classId,
        lessonDate,
        lessonTitle,
        userText: text,
        userContent: (message.content ?? []) as ThreadMessageLike["content"],
        placeholderContent: initialAssistantRunContent() ?? [],
        attachments: attachments.length ? attachments : undefined,
        currentMarkdown,
        chatStream,
      });
    },
    [chatStream, classId, draftId, draftKey, initialMarkdown, mode],
  );

  const onCancel = useCallback(async () => {
    cancelTurn(draftKey);
  }, [draftKey]);

  const turnActivity = workflowTurnActivity({
    localStreamActive: turn?.phase === "streaming",
    backendTurnInProgress:
      turn?.phase === "awaiting_backend" ||
      (turn == null && (storedDraft?.turnInProgress ?? turnInProgress) === true),
  });
  const runtime = useWorkflowChatRuntime({
    draftId: draftKey,
    isRunning: turnActivity.runtimeIsRunning,
    onNew,
    onCancel,
  });

  useEffect(() => {
    if (!patchDraft) return;
    if (skipPatchRef.current) {
      skipPatchRef.current = false;
      return;
    }
    if (artifactMarkdown === lastSyncedRef.current) return;

    if (patchTimerRef.current) clearTimeout(patchTimerRef.current);
    patchTimerRef.current = setTimeout(async () => {
      setSyncStatus("saving");
      try {
        const draft = await patchDraft(artifactMarkdown);
        lastSyncedRef.current = artifactMarkdown;
        useWorkflowDraftStore.getState().applyDraftPatch(draftKey, {
          artifactMarkdown,
          artifactRevision: draft.artifactRevision,
          artifactHash: draft.artifactHash,
          completeness: draft.completeness,
          readyToSave: draft.readyToSave,
        });
        setSyncStatus("idle");
      } catch {
        setSyncStatus("error");
      }
    }, 800);
    return () => {
      if (patchTimerRef.current) clearTimeout(patchTimerRef.current);
    };
  }, [artifactMarkdown, patchDraft, draftKey]);

  const isUpdating = turn?.phase === "streaming";

  const ctx = useMemo<ArtifactSessionContextValue>(
    () => ({
      classId,
      sessionId: storedDraft?.sessionId ?? recoveredSessionId,
      draftId: storedDraft?.draftId ?? draftId,
      artifactRevision: storedDraft?.artifactRevision ?? artifactRevision,
      artifactHash: storedDraft?.artifactHash ?? artifactHash,
      turnInProgress: storedDraft?.turnInProgress ?? turnInProgress,
      latestTurnComplete: storedDraft?.latestTurnComplete ?? latestTurnComplete,
      runWithSessionRecovery,
      artifactMarkdown,
      setArtifactMarkdown,
      completeness: storedDraft?.completeness ?? initialCompleteness,
      readyToSave: storedDraft?.readyToSave ?? false,
      lastChangeSummary: storedDraft?.lastChangeSummary ?? null,
      memoryState: storedDraft?.memoryState ?? initialMemoryState,
      memoryCandidates: storedDraft?.memoryCandidates ?? [],
      isUpdating,
      syncStatus,
      undo,
      redo,
      canUndo: editor.index > 0,
      canRedo: editor.index < editor.history.length - 1,
    }),
    [
      classId,
      storedDraft,
      recoveredSessionId,
      draftId,
      artifactRevision,
      artifactHash,
      turnInProgress,
      latestTurnComplete,
      runWithSessionRecovery,
      artifactMarkdown,
      setArtifactMarkdown,
      initialCompleteness,
      initialMemoryState,
      isUpdating,
      syncStatus,
      undo,
      redo,
      editor.index,
      editor.history.length,
    ],
  );

  return (
    <ArtifactSessionContext.Provider value={ctx}>
      <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>
    </ArtifactSessionContext.Provider>
  );
}
