export type MemoryFooterOperation = "idle" | "compiling" | "discarding";

export function getReadyToSaveButtonLabel(operation: MemoryFooterOperation): string {
  return operation === "compiling"
    ? "Compiling wiki updates..."
    : "Ready to save memory";
}
