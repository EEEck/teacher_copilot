import { WriteVerificationBlockedError } from "@/lib/api";

type ExecutiveFindingLike = {
  summary?: string;
  question?: string;
  severity?: string;
};

const DEFAULT_LEAD = "I didn't save this yet; one detail needs your call.";

function findingDetail(finding: ExecutiveFindingLike): string {
  return [finding.summary, finding.question].filter(Boolean).join(" — ");
}

function messageAlreadyIncludesFinding(
  message: string,
  finding: ExecutiveFindingLike,
): boolean {
  const parts = [finding.summary, finding.question]
    .map((part) => part?.trim())
    .filter((part): part is string => Boolean(part));
  if (parts.length === 0) return false;
  return parts.every((part) => message.includes(part));
}

/**
 * Format a write-verification 409 for teacher-facing copy (chat card / alert),
 * or null if not that error.
 *
 * When the payload message already embeds the finding text, prefer a short lead
 * + one bullet per finding so the card does not repeat the same prose twice.
 */
export function writeVerificationErrorMessage(error: unknown): string | null {
  if (!(error instanceof WriteVerificationBlockedError)) return null;
  const findings = Array.isArray(error.payload.executive_state?.open_findings)
    ? (error.payload.executive_state.open_findings as ExecutiveFindingLike[])
    : [];
  const blocking = findings.filter((item) => item.severity !== "advisory");
  const rawMessage = (error.payload.message || DEFAULT_LEAD).trim();
  const bullets = blocking
    .slice(0, 3)
    .map(findingDetail)
    .filter(Boolean)
    .map((detail) => `• ${detail}`);

  if (bullets.length === 0) return rawMessage;

  const expandedInMessage = blocking.every((finding) =>
    messageAlreadyIncludesFinding(rawMessage, finding),
  );
  const lead = expandedInMessage ? DEFAULT_LEAD : rawMessage;
  return [lead, ...bullets].join("\n");
}

/** Prefer write-verification copy, else Error.message, else fallback. */
export function errorMessageFromUnknown(
  error: unknown,
  fallback: string,
): string {
  return (
    writeVerificationErrorMessage(error) ??
    (error instanceof Error ? error.message : fallback)
  );
}
