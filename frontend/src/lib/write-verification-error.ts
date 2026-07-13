import { WriteVerificationBlockedError } from "@/lib/api";

type ExecutiveFindingLike = {
  summary?: string;
  question?: string;
  severity?: string;
};

/**
 * Format a write-verification 409 for the page Alert, or null if not that error.
 */
export function writeVerificationErrorMessage(error: unknown): string | null {
  if (!(error instanceof WriteVerificationBlockedError)) return null;
  const findings = Array.isArray(error.payload.executive_state?.open_findings)
    ? (error.payload.executive_state.open_findings as ExecutiveFindingLike[])
    : [];
  const blocking = findings.filter((item) => item.severity !== "advisory");
  const lines = [
    error.payload.message || "I didn't save this yet; one detail needs your call.",
  ];
  for (const finding of blocking.slice(0, 3)) {
    const detail = [finding.summary, finding.question].filter(Boolean).join(" — ");
    if (detail) lines.push(`• ${detail}`);
  }
  return lines.join("\n");
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
