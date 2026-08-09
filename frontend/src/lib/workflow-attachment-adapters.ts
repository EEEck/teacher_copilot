/**
 * assistant-ui AttachmentAdapters for artifact chat.
 * @see https://www.assistant-ui.com/docs/guides/attachments
 */
import {
  CompositeAttachmentAdapter,
  SimpleTextAttachmentAdapter,
  type AttachmentAdapter,
  type CompleteAttachment,
  type PendingAttachment,
} from "@assistant-ui/react";
import { client, type PlanMaterialSummary } from "@/lib/api";
import { getPlanMaterialArm } from "@/lib/plan-material-arm";

const materialByAttachmentId = new Map<string, PlanMaterialSummary>();
const materialErrorByAttachmentId = new Map<string, string>();

export function getPlanMaterialAttachmentError(id: string): string | undefined {
  return materialErrorByAttachmentId.get(id);
}

/** True while any composer attachment is still uploading / OCR-ing. */
export function composerHasRunningAttachments(
  attachments: ReadonlyArray<{ status: { type: string } }>,
): boolean {
  return attachments.some((a) => a.status.type === "running");
}

/** Text notes (.md / .txt) — kept as composer chips until send. */
class KlassenPilotTextAttachmentAdapter implements AttachmentAdapter {
  private readonly inner = new SimpleTextAttachmentAdapter();
  // Include extensions: browsers often leave File.type empty for .md.
  accept = `${this.inner.accept},.md,.txt,text/markdown`;

  add(state: { file: File }) {
    return this.inner.add(state);
  }

  send(attachment: PendingAttachment) {
    return this.inner.send(attachment);
  }

  remove() {
    return this.inner.remove();
  }
}

type MaterialsUploadContext = {
  getClassId: () => string;
  getSessionId: () => string;
};

/**
 * PDF → plan materials OCR on attach (optimistic tile while OCR runs).
 * On send, injects a short Material: citation into the user message text.
 */
class PlanMaterialsPdfAttachmentAdapter implements AttachmentAdapter {
  accept = "application/pdf,.pdf";

  constructor(private readonly ctx: MaterialsUploadContext) {}

  async *add({ file }: { file: File }): AsyncGenerator<PendingAttachment, void> {
    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      throw new Error("Only PDF class materials are supported here");
    }
    const maxSize = 40 * 1024 * 1024;
    if (file.size > maxSize) {
      throw new Error("PDF exceeds 40 MB limit");
    }
    const id = crypto.randomUUID();
    const base = {
      id,
      type: "document" as const,
      name: file.name,
      contentType: file.type || "application/pdf",
      file,
    };

    materialErrorByAttachmentId.delete(id);
    yield {
      ...base,
      // Progress required by assistant-ui typings; UI shows indeterminate copy.
      status: { type: "running", reason: "uploading", progress: 0 },
    };

    try {
      const classId = this.ctx.getClassId();
      const sessionId = this.ctx.getSessionId();
      if (!classId || !sessionId) {
        throw new Error("Plan session is not ready yet");
      }
      const summary = await client.planUploadMaterial(
        classId,
        sessionId,
        file,
        getPlanMaterialArm(),
      );
      materialByAttachmentId.set(id, summary);
      materialErrorByAttachmentId.delete(id);
      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent("kp:plan-materials-updated", { detail: summary }),
        );
      }
      yield {
        ...base,
        name: summary.title || file.name,
        status: { type: "requires-action", reason: "composer-send" },
      };
    } catch (err) {
      materialByAttachmentId.delete(id);
      const message =
        err instanceof Error ? err.message : "Materials OCR failed";
      materialErrorByAttachmentId.set(id, message);
      yield {
        ...base,
        status: { type: "incomplete", reason: "error" },
      };
      throw err instanceof Error ? err : new Error(message);
    }
  }

  async send(attachment: PendingAttachment): Promise<CompleteAttachment> {
    const summary = materialByAttachmentId.get(attachment.id);
    const cite = summary
      ? `Material: ${summary.material_id} (${summary.title || attachment.name})`
      : `Material PDF: ${attachment.name}`;
    const blurb = summary?.summary
      ? `\n${summary.summary.slice(0, 400)}${summary.summary.length > 400 ? "…" : ""}`
      : "";
    return {
      id: attachment.id,
      type: "document",
      name: attachment.name,
      contentType: attachment.contentType,
      file: attachment.file,
      status: { type: "complete" },
      content: [
        {
          type: "text",
          text: `[Uploaded class material — ${cite}]${blurb}`,
        },
      ],
    };
  }

  async remove(attachment: { id: string }): Promise<void> {
    materialByAttachmentId.delete(attachment.id);
    materialErrorByAttachmentId.delete(attachment.id);
  }
}

export function createIngestAttachmentAdapter(): AttachmentAdapter {
  return new KlassenPilotTextAttachmentAdapter();
}

export function createPlanAttachmentAdapter(ctx: MaterialsUploadContext): AttachmentAdapter {
  return new CompositeAttachmentAdapter([
    new KlassenPilotTextAttachmentAdapter(),
    new PlanMaterialsPdfAttachmentAdapter(ctx),
  ]);
}
