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
  useLocalRuntime,
  type ChatModelAdapter,
  type ThreadMessage,
} from "@assistant-ui/react";
import type { CompletenessChecklist } from "@/lib/api";
import { extractSessionAttachments, type SessionAttachment } from "@/lib/session-attachments";

export type ArtifactChatResult = {
  reply: string;
  artifactMarkdown: string;
  completeness?: CompletenessChecklist | null;
  readyToSave?: boolean;
};

export type ArtifactSessionConfig = {
  classId: string;
  sessionId: string;
  initialMarkdown: string;
  initialCompleteness?: CompletenessChecklist | null;
  chat: (args: {
    message: string;
    currentMarkdown: string;
    attachments?: SessionAttachment[];
  }) => Promise<ArtifactChatResult>;
  patchDraft?: (markdown: string) => Promise<{
    completeness?: CompletenessChecklist;
    readyToSave?: boolean;
  }>;
  onCompletenessChange?: (checklist: CompletenessChecklist) => void;
};

type ArtifactSessionContextValue = {
  classId: string;
  sessionId: string;
  artifactMarkdown: string;
  setArtifactMarkdown: (value: string, source?: "manual" | "agent") => void;
  completeness: CompletenessChecklist | null;
  readyToSave: boolean;
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

function extractText(message: ThreadMessage): string {
  return message.content
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
    sessionId,
    initialMarkdown,
    initialCompleteness = null,
    chat,
    patchDraft,
    onCompletenessChange,
  } = config;

  const [editor, setEditor] = useState<EditorState>({
    history: [initialMarkdown],
    index: 0,
  });
  const [completeness, setCompleteness] = useState<CompletenessChecklist | null>(initialCompleteness);
  const [readyToSave, setReadyToSave] = useState(false);
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
    (checklist: CompletenessChecklist | null | undefined, ready: boolean | undefined) => {
      if (checklist) {
        setCompleteness(checklist);
        onCompletenessChange?.(checklist);
      }
      if (ready !== undefined) setReadyToSave(ready);
    },
    [onCompletenessChange],
  );

  const adapter = useMemo<ChatModelAdapter>(
    () => ({
      async *run({ messages, abortSignal }) {
        const last = messages.at(-1);
        if (!last || last.role !== "user") return;

        setIsUpdating(true);
        try {
          const text = extractText(last);
          const attachments = await extractSessionAttachments(last);
          const currentMd =
            editorRef.current.history[editorRef.current.index] ?? initialMarkdown;
          const res = await chat({
            message: text,
            currentMarkdown: currentMd,
            attachments: attachments.length ? attachments : undefined,
          });
          pushMarkdown(res.artifactMarkdown, "agent");
          lastSyncedRef.current = res.artifactMarkdown;
          applyMeta(res.completeness ?? null, res.readyToSave);
          if (abortSignal?.aborted) return;
          yield { content: [{ type: "text", text: res.reply }] };
        } finally {
          setIsUpdating(false);
        }
      },
    }),
    [chat, initialMarkdown, pushMarkdown, applyMeta],
  );

  const runtime = useLocalRuntime(adapter);

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
        applyMeta(draft.completeness, draft.readyToSave);
        setSyncStatus("idle");
      } catch {
        setSyncStatus("error");
      }
    }, 800);
    return () => {
      if (patchTimerRef.current) clearTimeout(patchTimerRef.current);
    };
  }, [artifactMarkdown, patchDraft, applyMeta]);

  const ctx = useMemo<ArtifactSessionContextValue>(
    () => ({
      classId,
      sessionId,
      artifactMarkdown,
      setArtifactMarkdown,
      completeness,
      readyToSave,
      isUpdating,
      syncStatus,
      undo,
      redo,
      canUndo: editor.index > 0,
      canRedo: editor.index < editor.history.length - 1,
    }),
    [
      classId,
      sessionId,
      artifactMarkdown,
      setArtifactMarkdown,
      completeness,
      readyToSave,
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
