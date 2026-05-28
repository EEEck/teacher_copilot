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
import { client, type CompletenessChecklist } from "@/lib/api";

type IngestRuntimeContextValue = {
  sessionId: string;
  classId: string;
  diaryMarkdown: string;
  setDiaryMarkdown: (value: string, source?: "manual" | "agent") => void;
  completeness: CompletenessChecklist | null;
  readyToPropose: boolean;
  isUpdating: boolean;
  syncStatus: "idle" | "saving" | "error";
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
};

const IngestRuntimeContext = createContext<IngestRuntimeContextValue | null>(null);

export function useIngestRuntime() {
  const ctx = useContext(IngestRuntimeContext);
  if (!ctx) throw new Error("useIngestRuntime must be used within IngestRuntimeProvider");
  return ctx;
}

function extractText(message: ThreadMessage): string {
  return message.content
    .filter((part): part is { type: "text"; text: string } => part.type === "text")
    .map((part) => part.text)
    .join("\n");
}

type EditorState = { history: string[]; index: number };

export function IngestRuntimeProvider({
  classId,
  sessionId,
  initialDiaryMarkdown,
  initialCompleteness,
  onCompletenessChange,
  children,
}: {
  classId: string;
  sessionId: string;
  initialDiaryMarkdown: string;
  initialCompleteness: CompletenessChecklist | null;
  onCompletenessChange?: (checklist: CompletenessChecklist) => void;
  children: ReactNode;
}) {
  const [editor, setEditor] = useState<EditorState>({
    history: [initialDiaryMarkdown],
    index: 0,
  });
  const [completeness, setCompleteness] = useState<CompletenessChecklist | null>(
    initialCompleteness,
  );
  const [readyToPropose, setReadyToPropose] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"idle" | "saving" | "error">("idle");

  const diaryMarkdown = editor.history[editor.index] ?? initialDiaryMarkdown;
  const editorRef = useRef(editor);
  editorRef.current = editor;
  const skipPatchRef = useRef(true);
  const lastSyncedRef = useRef(initialDiaryMarkdown);
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

  const setDiaryMarkdown = useCallback(
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

  const applyCompleteness = useCallback(
    (checklist: CompletenessChecklist, ready: boolean) => {
      setCompleteness(checklist);
      setReadyToPropose(ready);
      onCompletenessChange?.(checklist);
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
          const currentMd =
            editorRef.current.history[editorRef.current.index] ?? initialDiaryMarkdown;
          const res = await client.ingestChat(classId, sessionId, text, currentMd);
          pushMarkdown(res.diary_markdown, "agent");
          lastSyncedRef.current = res.diary_markdown;
          applyCompleteness(res.completeness, res.ready_to_propose);
          if (abortSignal?.aborted) return;
          yield { content: [{ type: "text", text: res.reply }] };
        } finally {
          setIsUpdating(false);
        }
      },
    }),
    [classId, sessionId, initialDiaryMarkdown, pushMarkdown, applyCompleteness],
  );

  const runtime = useLocalRuntime(adapter);

  useEffect(() => {
    if (skipPatchRef.current) {
      skipPatchRef.current = false;
      return;
    }
    if (diaryMarkdown === lastSyncedRef.current) return;

    if (patchTimerRef.current) clearTimeout(patchTimerRef.current);
    patchTimerRef.current = setTimeout(async () => {
      setSyncStatus("saving");
      try {
        const draft = await client.ingestUpdateDraft(classId, sessionId, diaryMarkdown);
        lastSyncedRef.current = diaryMarkdown;
        const ready = draft.completeness.items.every((i) => !i.required || i.complete);
        applyCompleteness(draft.completeness, ready);
        setSyncStatus("idle");
      } catch {
        setSyncStatus("idle");
      }
    }, 800);
    return () => {
      if (patchTimerRef.current) clearTimeout(patchTimerRef.current);
    };
  }, [classId, sessionId, diaryMarkdown, applyCompleteness]);

  const ctx = useMemo<IngestRuntimeContextValue>(
    () => ({
      classId,
      sessionId,
      diaryMarkdown,
      setDiaryMarkdown,
      completeness,
      readyToPropose,
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
      diaryMarkdown,
      setDiaryMarkdown,
      completeness,
      readyToPropose,
      isUpdating,
      syncStatus,
      undo,
      redo,
      editor.index,
      editor.history.length,
    ],
  );

  return (
    <IngestRuntimeContext.Provider value={ctx}>
      <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>
    </IngestRuntimeContext.Provider>
  );
}
