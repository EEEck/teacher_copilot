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
} from "@assistant-ui/react";
import { isUnknownSessionError, type ChatMessage, type CompletenessChecklist } from "@/lib/api";
import type { MemoryCandidate } from "@/lib/api";
import type { ChatStreamChunk } from "@/components/assistant-ui/artifact-runtime-config";
import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";
import { initialAssistantRunContent, lessonContextFromMemoryState } from "@/lib/chat-run-feedback";
import {
  clearPendingChatTurn,
  markPendingChatTurn,
} from "@/lib/pending-chat-turns";
import { extractSessionAttachments, type SessionAttachment } from "@/lib/session-attachments";
import { streamPartsToRunContent } from "@/lib/sse-chat";
import { useWorkflowChatRuntime, type UpdateWorkflowThread } from "@/features/workflow-drafts/workflow-chat-runtime";
import { workflowTurnActivity } from "@/features/workflow-drafts/workflow-turn-activity";
import {
  newThreadMessageId,
  replaceLastAssistantContent,
} from "@/features/workflow-drafts/thread-messages";
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

const CHAT_ERROR_REPLY =
  "I could not finish that turn. Your draft is unchanged — try a shorter message or one topic at a time.";

function friendlyChatError(err: unknown): string {
  const raw = err instanceof Error ? err.message : "Something went wrong";
  if (/max turns/i.test(raw) || /API 5\d\d/i.test(raw)) {
    return CHAT_ERROR_REPLY;
  }
  if (raw.startsWith("API ")) {
    return CHAT_ERROR_REPLY;
  }
  return raw;
}

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
    initialMessages,
    initialCompleteness = null,
    initialMemoryState = null,
    chatStream,
    patchDraft,
    getSessionId: configGetSessionId,
    onSessionLost,
    onCompletenessChange,
  } = config;

  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = configGetSessionId?.() ?? sessionId;
  const [activeSessionId, setActiveSessionId] = useState(sessionId);
  const [activeDraftId, setActiveDraftId] = useState(draftId);
  const [activeArtifactRevision, setActiveArtifactRevision] = useState(artifactRevision);
  const [activeArtifactHash, setActiveArtifactHash] = useState(artifactHash);
  const [activeTurnInProgress, setActiveTurnInProgress] = useState(turnInProgress);
  const [activeLatestTurnComplete, setActiveLatestTurnComplete] =
    useState(latestTurnComplete);
  const activeDraftIdRef = useRef(draftId);
  activeDraftIdRef.current = activeDraftId;
  const storedDraft = useWorkflowDraftStore(
    (state) => state.draftsById[activeDraftId || activeSessionId],
  );

  useEffect(() => {
    sessionIdRef.current = configGetSessionId?.() ?? sessionId;
    setActiveSessionId(sessionIdRef.current);
    setActiveDraftId(draftId);
    setActiveArtifactRevision(artifactRevision);
    setActiveArtifactHash(artifactHash);
    setActiveTurnInProgress(turnInProgress);
    setActiveLatestTurnComplete(latestTurnComplete);
  }, [
    sessionId,
    configGetSessionId,
    draftId,
    artifactRevision,
    artifactHash,
    turnInProgress,
    latestTurnComplete,
  ]);

  const [editor, setEditor] = useState<EditorState>({
    history: [initialMarkdown],
    index: 0,
  });
  const [completeness, setCompleteness] = useState<CompletenessChecklist | null>(initialCompleteness);
  const [readyToSave, setReadyToSave] = useState(false);
  const [lastChangeSummary, setLastChangeSummary] = useState<string | null>(null);
  const [memoryState, setMemoryState] = useState<Record<string, unknown> | null>(
    initialMemoryState,
  );
  const memoryStateRef = useRef(memoryState);
  memoryStateRef.current = memoryState;
  const configLessonDateRef = useRef(configLessonDate);
  configLessonDateRef.current = configLessonDate;
  const configLessonTitleRef = useRef(configLessonTitle);
  configLessonTitleRef.current = configLessonTitle;
  const [isUpdating, setIsUpdating] = useState(false);
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

  useEffect(() => {
    if (!storedDraft) return;
    setActiveSessionId(storedDraft.sessionId);
    setActiveDraftId(storedDraft.draftId);
    setActiveArtifactRevision(storedDraft.artifactRevision);
    setActiveArtifactHash(storedDraft.artifactHash);
    setActiveTurnInProgress(storedDraft.turnInProgress);
    setActiveLatestTurnComplete(storedDraft.latestTurnComplete);
    if (storedDraft.artifactMarkdown !== lastSyncedRef.current) {
      pushMarkdown(storedDraft.artifactMarkdown, "agent");
    }
  }, [storedDraft, pushMarkdown]);

  // Backend draft refreshes (background turn completion) must update the editor
  // without remounting the assistant-ui runtime.
  useEffect(() => {
    if (initialMarkdown === lastSyncedRef.current) return;
    pushMarkdown(initialMarkdown, "agent");
  }, [artifactRevision, artifactHash, initialMarkdown, pushMarkdown]);

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

  const applyMeta = useCallback(
    (
      checklist: CompletenessChecklist | null | undefined,
      ready: boolean | undefined,
      result?: Pick<ArtifactChatResult, "lastChangeSummary" | "memoryState">,
    ) => {
      if (checklist) {
        setCompleteness(checklist);
        onCompletenessChange?.(checklist);
      }
      if (ready !== undefined) setReadyToSave(ready);
      if (result?.lastChangeSummary !== undefined) {
        setLastChangeSummary(result.lastChangeSummary ?? null);
      }
      if (result?.memoryState !== undefined) {
        setMemoryState(result.memoryState ?? null);
      }
    },
    [onCompletenessChange],
  );

  const applyDraftMetadata = useCallback(
    (metadata?: {
      draftId?: string;
      artifactRevision?: number;
      artifactHash?: string;
      turnInProgress?: boolean;
      latestTurnComplete?: boolean;
    }) => {
      if (!metadata) return;
      if (metadata.draftId !== undefined) setActiveDraftId(metadata.draftId);
      if (metadata.artifactRevision !== undefined) {
        setActiveArtifactRevision(metadata.artifactRevision);
      }
      if (metadata.artifactHash !== undefined) setActiveArtifactHash(metadata.artifactHash);
      if (metadata.turnInProgress !== undefined) {
        setActiveTurnInProgress(metadata.turnInProgress);
      }
      if (metadata.latestTurnComplete !== undefined) {
        setActiveLatestTurnComplete(metadata.latestTurnComplete);
      }
    },
    [],
  );

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
        setActiveSessionId(sessionIdRef.current);
        return await run(sessionIdRef.current);
      }
    },
    [initialMarkdown, onSessionLost, configGetSessionId, sessionId],
  );

  const onNew = useCallback(
    async (message: AppendMessage, updateThread: UpdateWorkflowThread) => {
      if (message.role !== "user") return;

      const userContent = message.content ?? [];
      const startingContent = initialAssistantRunContent() ?? [];

      updateThread((messages) => [
        ...messages,
        {
          id: newThreadMessageId("user"),
          role: "user",
          content: userContent,
        },
        {
          id: newThreadMessageId("assistant"),
          role: "assistant",
          content: startingContent,
        },
      ]);
      setIsUpdating(true);
      const fromMemory = lessonContextFromMemoryState(memoryStateRef.current);
      const lessonDate =
        fromMemory.lessonDate ||
        configLessonDateRef.current.trim() ||
        undefined;
      const lessonTitle =
        fromMemory.lessonTitle ||
        configLessonTitleRef.current.trim() ||
        undefined;
      const pendingKey =
        typeof window !== "undefined"
          ? markPendingChatTurn(window.sessionStorage, {
              mode,
              classId,
              sessionId: sessionIdRef.current,
              draftId: activeDraftIdRef.current || undefined,
              lessonDate,
              lessonTitle,
              resumeHref: `${window.location.pathname}${window.location.search}`,
            })
          : "";
      // Successful turns leave the pending marker for PendingTurnNotifier.
      // Failed client streams clear it so the notifier does not toast a false completion.
      let turnFailed = false;
      try {
        const text = extractText(message);
        const attachments = await extractSessionAttachments(
          message as unknown as Parameters<typeof extractSessionAttachments>[0],
        );
        const currentMd =
          editorRef.current.history[editorRef.current.index] ?? initialMarkdown;
        let finalResult: ArtifactChatResult | null = null;
        for await (const chunk of chatStream({
          message: text,
          currentMarkdown: currentMd,
          attachments: attachments.length ? attachments : undefined,
        })) {
          if (chunk.kind === "progress") {
            if (chunk.content.length > 0) {
              updateThread((messages) =>
                replaceLastAssistantContent(
                  messages,
                  streamPartsToRunContent(chunk.content) ?? [],
                ),
              );
            }
            continue;
          }
          finalResult = chunk.result;
          pushMarkdown(chunk.result.artifactMarkdown, "agent");
          lastSyncedRef.current = chunk.result.artifactMarkdown;
          applyDraftMetadata(chunk.result);
          applyMeta(chunk.result.completeness ?? null, chunk.result.readyToSave, chunk.result);
          const content =
            chunk.content.length > 0
              ? streamPartsToRunContent(chunk.content)
              : [{ type: "text" as const, text: chunk.result.reply }];
          updateThread((messages) =>
            replaceLastAssistantContent(messages, content ?? []),
          );
        }
        if (!finalResult) {
          turnFailed = true;
          updateThread((messages) =>
            replaceLastAssistantContent(messages, [{ type: "text", text: CHAT_ERROR_REPLY }]),
          );
        }
      } catch (err) {
        const reply = friendlyChatError(err);
        turnFailed = true;
        updateThread((messages) =>
          replaceLastAssistantContent(messages, [{ type: "text", text: reply }]),
        );
      } finally {
        if (turnFailed && pendingKey && typeof window !== "undefined") {
          clearPendingChatTurn(window.sessionStorage, pendingKey);
        }
        setIsUpdating(false);
      }
    },
    [
      applyDraftMetadata,
      applyMeta,
      chatStream,
      classId,
      initialMarkdown,
      mode,
      pushMarkdown,
    ],
  );

  const turnActivity = workflowTurnActivity({
    localStreamActive: isUpdating,
    backendTurnInProgress: activeTurnInProgress,
  });
  const runtime = useWorkflowChatRuntime({
    draftId: activeDraftId || activeSessionId,
    isRunning: turnActivity.runtimeIsRunning,
    onNew,
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
        applyDraftMetadata(draft);
        applyMeta(draft.completeness, draft.readyToSave);
        setSyncStatus("idle");
      } catch {
        setSyncStatus("error");
      }
    }, 800);
    return () => {
      if (patchTimerRef.current) clearTimeout(patchTimerRef.current);
    };
  }, [artifactMarkdown, patchDraft, applyMeta, applyDraftMetadata]);

  const ctx = useMemo<ArtifactSessionContextValue>(
    () => ({
      classId,
      sessionId: activeSessionId,
      draftId: activeDraftId,
      artifactRevision: activeArtifactRevision,
      artifactHash: activeArtifactHash,
      turnInProgress: activeTurnInProgress,
      latestTurnComplete: activeLatestTurnComplete,
      runWithSessionRecovery,
      artifactMarkdown,
      setArtifactMarkdown,
      completeness,
      readyToSave,
      lastChangeSummary,
      memoryState,
      isUpdating,
      syncStatus,
      undo,
      redo,
      canUndo: editor.index > 0,
      canRedo: editor.index < editor.history.length - 1,
    }),
    [
      classId,
      activeSessionId,
      activeDraftId,
      activeArtifactRevision,
      activeArtifactHash,
      activeTurnInProgress,
      activeLatestTurnComplete,
      runWithSessionRecovery,
      artifactMarkdown,
      setArtifactMarkdown,
      completeness,
      readyToSave,
      lastChangeSummary,
      memoryState,
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
