/** Teacher-facing copy for failed/interrupted chat turns (runner + store). */

export const CHAT_ERROR_REPLY =
  "I could not finish that turn. Your draft is unchanged — try a shorter message or one topic at a time.";

export function friendlyChatError(err: unknown): string {
  const raw = err instanceof Error ? err.message : "Something went wrong";
  if (/max turns/i.test(raw) || /API 5\d\d/i.test(raw)) {
    return CHAT_ERROR_REPLY;
  }
  if (raw.startsWith("API ")) {
    return CHAT_ERROR_REPLY;
  }
  return raw;
}
