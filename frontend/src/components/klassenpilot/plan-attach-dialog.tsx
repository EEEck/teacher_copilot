"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { FileText, UploadIcon } from "lucide-react";
import { useAui } from "@assistant-ui/react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { SegmentedToggle } from "@/components/ui/segmented-toggle";
import { cn } from "@/lib/utils";
import {
  setPlanMaterialArm,
  type PlanMaterialArm,
} from "@/lib/plan-material-arm";

const ARM_OPTIONS = [
  { value: "textbook", label: "Textbook" },
  { value: "personal", label: "Personal" },
];

export function isPlanPdfFile(file: File): boolean {
  return (
    file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")
  );
}

export function isPlanTextNoteFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return (
    name.endsWith(".md") ||
    name.endsWith(".txt") ||
    file.type === "text/plain" ||
    file.type === "text/markdown"
  );
}

type PlanAttachContextValue = {
  openAttachDialog: (stagedFile?: File | null) => void;
};

const PlanAttachContext = createContext<PlanAttachContextValue | null>(null);

export function usePlanAttachOptional(): PlanAttachContextValue | null {
  return useContext(PlanAttachContext);
}

export function PlanAttachProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [stagedFile, setStagedFile] = useState<File | null>(null);

  const openAttachDialog = useCallback((file?: File | null) => {
    setStagedFile(file ?? null);
    setOpen(true);
  }, []);

  const handleOpenChange = useCallback((next: boolean) => {
    setOpen(next);
    if (!next) setStagedFile(null);
  }, []);

  return (
    <PlanAttachContext.Provider value={{ openAttachDialog }}>
      {children}
      <PlanAttachDialog
        open={open}
        onOpenChange={handleOpenChange}
        stagedFile={stagedFile}
        onStagedFileChange={setStagedFile}
      />
    </PlanAttachContext.Provider>
  );
}

type PlanAttachDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  stagedFile: File | null;
  onStagedFileChange: (file: File | null) => void;
};

function PlanAttachDialog({
  open,
  onOpenChange,
  stagedFile,
  onStagedFileChange,
}: PlanAttachDialogProps) {
  const aui = useAui();
  const pdfInputId = useId();
  const notesInputId = useId();
  const pdfInputRef = useRef<HTMLInputElement>(null);
  const notesInputRef = useRef<HTMLInputElement>(null);
  const [arm, setArm] = useState<PlanMaterialArm>("textbook");
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setBusy(false);
      setError(null);
      setDragging(false);
      setArm("textbook");
    }
  }, [open]);

  const uploadPdf = useCallback(
    (file: File) => {
      setError(null);
      setPlanMaterialArm(arm);
      // Optimistic: close dialog immediately; OCR continues on the composer tile.
      onOpenChange(false);
      onStagedFileChange(null);
      void aui
        .composer()
        .addAttachment(file)
        .catch((err: unknown) => {
          toast.error(err instanceof Error ? err.message : "PDF upload failed");
        });
    },
    [arm, aui, onOpenChange, onStagedFileChange],
  );

  const attachNotes = useCallback(
    async (file: File) => {
      setBusy(true);
      setError(null);
      try {
        await aui.composer().addAttachment(file);
        onOpenChange(false);
        onStagedFileChange(null);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Could not attach notes";
        setError(message);
        toast.error(message);
      } finally {
        setBusy(false);
      }
    },
    [aui, onOpenChange, onStagedFileChange],
  );

  const takeFirstPdf = (files: FileList | File[] | null) => {
    const list = files ? Array.from(files) : [];
    return list.find(isPlanPdfFile) ?? null;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md"
        data-testid="plan-attach-dialog"
        onDragEnter={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          const next = e.relatedTarget as Node | null;
          if (next && e.currentTarget.contains(next)) return;
          setDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const pdf = takeFirstPdf(e.dataTransfer.files);
          if (pdf) {
            onStagedFileChange(pdf);
            setError(null);
          } else {
            setError("Drop a PDF textbook or personal material");
          }
        }}
      >
        <DialogHeader>
          <DialogTitle>Attach class material</DialogTitle>
          <DialogDescription>
            Choose Textbook or Personal, then drop or browse a PDF. Upload
            closes this dialog; reading continues on a composer tile.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <SegmentedToggle
            aria-label="PDF material type"
            value={arm}
            onValueChange={(v) => setArm(v as PlanMaterialArm)}
            options={ARM_OPTIONS}
          />

          <div
            className={cn(
              "flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-8 text-center transition-colors",
              dragging
                ? "border-ring bg-accent/50"
                : "border-border bg-muted/40",
            )}
          >
            <UploadIcon className="size-6 text-muted-foreground" />
            <p className="text-sm font-medium text-foreground">
              Drag a PDF here
            </p>
            <p className="text-xs text-muted-foreground">
              or browse from your computer
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => pdfInputRef.current?.click()}
            >
              Browse files
            </Button>
            <input
              id={pdfInputId}
              ref={pdfInputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="sr-only"
              data-testid="plan-attach-pdf-input"
              disabled={busy}
              onChange={(e) => {
                const pdf = takeFirstPdf(e.target.files);
                e.target.value = "";
                if (pdf) {
                  onStagedFileChange(pdf);
                  setError(null);
                }
              }}
            />
          </div>

          {stagedFile ? (
            <div className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm">
              <FileText className="size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate font-medium">
                {stagedFile.name}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="xs"
                disabled={busy}
                onClick={() => onStagedFileChange(null)}
              >
                Clear
              </Button>
            </div>
          ) : null}

          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}

          <div className="flex justify-start">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="px-0 text-muted-foreground"
              disabled={busy}
              onClick={() => notesInputRef.current?.click()}
            >
              Attach .md / .txt notes
            </Button>
            <input
              id={notesInputId}
              ref={notesInputRef}
              type="file"
              accept=".md,.txt,text/plain,text/markdown"
              className="sr-only"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (!file) return;
                if (!isPlanTextNoteFile(file)) {
                  setError("Only .md or .txt notes are supported here");
                  return;
                }
                void attachNotes(file);
              }}
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="default"
            disabled={busy || !stagedFile}
            onClick={() => {
              if (stagedFile) uploadPdf(stagedFile);
            }}
          >
            Upload PDF
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
