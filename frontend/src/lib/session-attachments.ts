import type { ThreadMessage } from "@assistant-ui/react";

const MAX_ATTACHMENT_BYTES = 64_000;
const ALLOWED_EXTENSIONS = [".md", ".txt"];

export type SessionAttachment = { filename: string; content: string };

function isAllowedFilename(name: string): boolean {
  const lower = name.toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

async function readFileText(file: File): Promise<string | null> {
  if (!isAllowedFilename(file.name)) return null;
  if (file.size > MAX_ATTACHMENT_BYTES) return null;
  return file.text();
}

/** Collect .md / .txt attachments from the latest user message. */
export async function extractSessionAttachments(
  message: ThreadMessage,
): Promise<SessionAttachment[]> {
  const out: SessionAttachment[] = [];

  const attachments = (message as ThreadMessage & { attachments?: { name?: string; file?: File }[] })
    .attachments;
  if (attachments?.length) {
    for (const att of attachments) {
      const name = att.name ?? "attachment.txt";
      if (att.file) {
        const content = await readFileText(att.file);
        if (content) out.push({ filename: name, content });
      }
    }
  }

  for (const part of message.content) {
    if (part.type === "file" && "file" in part && part.file instanceof File) {
      const content = await readFileText(part.file);
      if (content) out.push({ filename: part.file.name, content });
    }
  }

  return out;
}
