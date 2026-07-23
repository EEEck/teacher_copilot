# Frontend Lib

Small shared utilities and API helpers.

## Files

- `api.ts` - backend HTTP client helpers and response types, including
  `IngestStartHint` for optional Update Memory lesson/date hints and Memory
  Sweep review session endpoints.
- `sse-chat.ts` - SSE event parsing for chat streams.
- `sse-chat.test.ts` - Vitest coverage for SSE parsing.
- `session-attachments.ts` - attachment handling helpers.
- `markdown-diff.ts` - markdown diff utilities for review UI.
- `diary-utils.ts` - diary artifact helpers.
- `review-brief.ts` - teacher-first grouping for proposed wiki file changes.
- `sweep-brief.ts` - teacher-first grouping for Memory Sweep candidates.
- `running-jobs.ts` - Running-job union (poll ∪ local runners)
  (plan/ingest turns and `memory_sweep` generation). Claimed once by the
  global pending-turn notifier.
- `chat-run-feedback.ts` - labels for the Running box and completion toasts.
- `memory-sweep-review-status.ts` - class-home badge text and sweep loading
  copy. “Stale draft” only when teacher edits are at risk.
- `pending-memory-review.ts` - session-storage helper for prepared, non-durable
  memory reviews.
- `memory-save-guards.ts` - review save/double-save guard logic.
- `class-home-refresh.ts` - one-shot class-home timeline refresh markers.
- `utils.ts` - generic utility helpers.

## Conventions

- Keep network shape changes in sync with `backend/app/schemas/api.py`.
- Keep Memory Sweep types aligned with `../../../docs/mem_v4/README.md`,
  `../../../docs/agent_contracts.md`, and backend `app/schemas/api.py`.
- Keep frontend hint union types aligned with backend literal schema values.
- Pending-job markers are UI/operation coordination only; they never authorize
  wiki writes.
- Add focused tests for parser/utility behavior when the logic is not trivial.
