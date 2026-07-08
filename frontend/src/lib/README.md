# Frontend Lib

Small shared utilities and API helpers.

## Files

- `api.ts` - backend HTTP client helpers and response types, including
  `IngestStartHint` for optional Update Memory lesson/date hints.
- `sse-chat.ts` - SSE event parsing for chat streams.
- `sse-chat.test.ts` - Vitest coverage for SSE parsing.
- `session-attachments.ts` - attachment handling helpers.
- `markdown-diff.ts` - markdown diff utilities for review UI.
- `diary-utils.ts` - diary artifact helpers.
- `review-brief.ts` - teacher-first grouping for proposed wiki file changes.
- `sweep-brief.ts` - teacher-first grouping for Memory Sweep candidates.
- `pending-memory-review.ts` - session-storage helper for prepared, non-durable
  memory reviews.
- `memory-save-guards.ts` - review save/double-save guard logic.
- `utils.ts` - generic utility helpers.

## Conventions

- Keep network shape changes in sync with `backend/app/schemas/api.py`.
- Keep Memory Sweep types aligned with `../../../docs/mem_v3/README.md` and
  backend `app/schemas/api.py`.
- Keep frontend hint union types aligned with backend literal schema values.
- Add focused tests for parser/utility behavior when the logic is not trivial.
