"use client";

import {
  type PropsWithChildren,
  useEffect,
  useState,
  type FC,
  type ReactNode,
} from "react";
import {
  XIcon,
  PlusIcon,
  FileText,
  Loader2Icon,
  AlertCircleIcon,
  CheckIcon,
} from "lucide-react";
import {
  AttachmentPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  useAuiState,
  useAui,
} from "@assistant-ui/react";
import { useShallow } from "zustand/shallow";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { usePlanAttachOptional } from "@/components/klassenpilot/plan-attach-dialog";
import { getPlanMaterialAttachmentError } from "@/lib/workflow-attachment-adapters";
import { cn } from "@/lib/utils";

const useFileSrc = (file: File | undefined) => {
  const [src, setSrc] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!file) {
      setSrc(undefined);
      return;
    }

    const objectUrl = URL.createObjectURL(file);
    setSrc(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [file]);

  return src;
};

const useAttachmentSrc = () => {
  const { file, src } = useAuiState(
    useShallow((s): { file?: File; src?: string } => {
      if (s.attachment.type !== "image") return {};
      if (s.attachment.file) return { file: s.attachment.file };
      const src = s.attachment.content?.filter((c) => c.type === "image")[0]
        ?.image;
      if (!src) return {};
      return { src };
    }),
  );

  return useFileSrc(file) ?? src;
};

type AttachmentPreviewProps = {
  src: string;
};

const AttachmentPreview: FC<AttachmentPreviewProps> = ({ src }) => {
  const [isLoaded, setIsLoaded] = useState(false);
  return (
    <img
      src={src}
      alt="Attachment preview"
      className={cn(
        "block h-auto max-h-[80vh] w-auto max-w-full object-contain",
        isLoaded
          ? "aui-attachment-preview-image-loaded"
          : "aui-attachment-preview-image-loading invisible",
      )}
      onLoad={() => setIsLoaded(true)}
    />
  );
};

const AttachmentPreviewDialog: FC<PropsWithChildren> = ({ children }) => {
  const src = useAttachmentSrc();

  if (!src) return children;

  return (
    <Dialog>
      <DialogTrigger
        className="aui-attachment-preview-trigger cursor-pointer transition-colors hover:bg-accent/50"
        asChild
      >
        {children}
      </DialogTrigger>
      <DialogContent className="aui-attachment-preview-dialog-content p-2 sm:max-w-3xl [&>button]:rounded-full [&>button]:bg-foreground/60 [&>button]:p-1 [&>button]:opacity-100 [&>button]:ring-0! [&_svg]:text-background [&>button]:hover:[&_svg]:text-destructive">
        <DialogTitle className="aui-sr-only sr-only">
          Image Attachment Preview
        </DialogTitle>
        <div className="aui-attachment-preview relative mx-auto flex max-h-[80dvh] w-full items-center justify-center overflow-hidden bg-background">
          <AttachmentPreview src={src} />
        </div>
      </DialogContent>
    </Dialog>
  );
};

const AttachmentThumb: FC = () => {
  const src = useAttachmentSrc();

  return (
    <Avatar className="aui-attachment-tile-avatar h-full w-full rounded-none">
      <AvatarImage
        src={src}
        alt="Attachment preview"
        className="aui-attachment-tile-image object-cover"
      />
      <AvatarFallback>
        <FileText className="aui-attachment-tile-fallback-icon size-8 text-muted-foreground" />
      </AvatarFallback>
    </Avatar>
  );
};

const AttachmentUI: FC = () => {
  const aui = useAui();
  const isComposer = aui.attachment.source !== "message";

  const isImage = useAuiState((s) => s.attachment.type === "image");
  const typeLabel = useAuiState((s) => {
    const type = s.attachment.type;
    switch (type) {
      case "image":
        return "Image";
      case "document":
        return "Document";
      case "file":
        return "File";
      default:
        return type;
    }
  });

  const attachmentId = useAuiState((s) => s.attachment.id);
  const uploadState = useAuiState((s) => {
    const status = s.attachment.status;
    if (status.type === "running") return "uploading" as const;
    if (status.type === "incomplete" && status.reason === "error") {
      return "error" as const;
    }
    if (
      isComposer &&
      status.type === "requires-action" &&
      status.reason === "composer-send"
    ) {
      return "ready" as const;
    }
    return undefined;
  });
  const isUploading = uploadState === "uploading";
  const isError = uploadState === "error";
  const isReady = uploadState === "ready";
  const errorMessage = isError
    ? getPlanMaterialAttachmentError(attachmentId) ?? "Upload failed"
    : null;

  return (
    <TooltipProvider>
      <Tooltip>
        <AttachmentPrimitive.Root
          className={cn(
            "aui-attachment-root relative",
            isImage &&
              !isComposer &&
              "aui-attachment-root-message only:*:first:size-24",
          )}
        >
          <AttachmentPreviewDialog>
            <TooltipTrigger asChild>
              <div
                className={cn(
                  "aui-attachment-tile relative size-14 cursor-pointer overflow-hidden rounded-[calc(var(--composer-radius)-var(--composer-padding))] border bg-muted transition-opacity hover:opacity-75",
                  isError && "border-destructive",
                  isReady && "border-primary/40",
                )}
                role="button"
                tabIndex={0}
                aria-label={`${typeLabel} attachment${
                  isError
                    ? ", upload failed"
                    : isUploading
                      ? ", reading PDF"
                      : isReady
                        ? ", ready"
                        : ""
                }`}
              >
                <AttachmentThumb />
                {isUploading && (
                  <div
                    aria-hidden="true"
                    className="aui-attachment-tile-uploading absolute inset-0 flex flex-col items-center justify-center gap-0.5 bg-background/60 px-1 backdrop-blur-[1px]"
                  >
                    <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
                    <span className="text-center text-[9px] font-medium leading-tight text-muted-foreground">
                      Reading PDF…
                    </span>
                  </div>
                )}
                {isError && (
                  <div
                    aria-hidden="true"
                    className="aui-attachment-tile-error absolute inset-0 flex items-center justify-center bg-destructive/10"
                  >
                    <AlertCircleIcon className="size-5 text-destructive" />
                  </div>
                )}
                {isReady && (
                  <div
                    aria-hidden="true"
                    className="aui-attachment-tile-ready absolute right-0.5 bottom-0.5 flex size-4 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm"
                  >
                    <CheckIcon className="size-2.5" strokeWidth={3} />
                  </div>
                )}
              </div>
            </TooltipTrigger>
          </AttachmentPreviewDialog>
          {isComposer && <AttachmentRemove />}
        </AttachmentPrimitive.Root>
        <TooltipContent side="top">
          <AttachmentPrimitive.Name />
          {isUploading ? (
            <p className="text-muted-foreground">Reading PDF…</p>
          ) : null}
          {isReady ? (
            <p className="text-muted-foreground">Ready to send</p>
          ) : null}
          {isError && errorMessage ? (
            <p className="aui-attachment-error-message text-destructive">
              {errorMessage}
            </p>
          ) : null}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

const AttachmentRemove: FC = () => {
  return (
    <AttachmentPrimitive.Remove asChild>
      <TooltipIconButton
        tooltip="Remove file"
        className="aui-attachment-tile-remove absolute end-1.5 top-1.5 size-3.5 rounded-full bg-white text-muted-foreground opacity-100 shadow-sm hover:bg-white! [&_svg]:text-black hover:[&_svg]:text-destructive"
        side="top"
      >
        <XIcon className="aui-attachment-remove-icon size-3 dark:stroke-[2.5px]" />
      </TooltipIconButton>
    </AttachmentPrimitive.Remove>
  );
};

export const UserMessageAttachments: FC = () => {
  return (
    <div className="aui-user-message-attachments-end col-span-full col-start-1 row-start-1 flex w-full flex-row justify-end gap-2">
      <MessagePrimitive.Attachments>
        {() => <AttachmentUI />}
      </MessagePrimitive.Attachments>
    </div>
  );
};

export const ComposerAttachments: FC = () => {
  return (
    <div className="aui-composer-attachments flex w-full flex-row items-center gap-2 overflow-x-auto empty:hidden">
      <ComposerPrimitive.Attachments>
        {() => <AttachmentUI />}
      </ComposerPrimitive.Attachments>
    </div>
  );
};

export const ComposerAddAttachment: FC<{
  tooltip?: string;
}> = ({ tooltip = "Add Attachment" }) => {
  const planAttach = usePlanAttachOptional();

  if (planAttach) {
    return (
      <TooltipIconButton
        tooltip={tooltip}
        side="bottom"
        variant="ghost"
        size="icon"
        className="aui-composer-add-attachment size-8 rounded-full p-1 font-semibold text-xs hover:bg-muted-foreground/15 dark:border-muted-foreground/15 dark:hover:bg-muted-foreground/30"
        aria-label={tooltip}
        onClick={() => planAttach.openAttachDialog(null)}
      >
        <PlusIcon className="aui-attachment-add-icon size-5 stroke-[1.5px]" />
      </TooltipIconButton>
    );
  }

  return (
    <ComposerPrimitive.AddAttachment asChild>
      <TooltipIconButton
        tooltip={tooltip}
        side="bottom"
        variant="ghost"
        size="icon"
        className="aui-composer-add-attachment size-8 rounded-full p-1 font-semibold text-xs hover:bg-muted-foreground/15 dark:border-muted-foreground/15 dark:hover:bg-muted-foreground/30"
        aria-label={tooltip}
      >
        <PlusIcon className="aui-attachment-add-icon size-5 stroke-[1.5px]" />
      </TooltipIconButton>
    </ComposerPrimitive.AddAttachment>
  );
};

/** Left side of composer actions: optional controls + +. */
export const ComposerAttachmentControls: FC<{
  leading?: ReactNode;
  addTooltip?: string;
}> = ({ leading, addTooltip }) => {
  return (
    <div className="flex items-center gap-2">
      {leading}
      <ComposerAddAttachment tooltip={addTooltip} />
    </div>
  );
};
