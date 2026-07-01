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
- `utils.ts` - generic utility helpers.

## Conventions

- Keep network shape changes in sync with `backend/app/schemas/api.py`.
- Keep Memory Sweep types aligned with `../../../docs/mem_v2/frontend.md`.
- Keep frontend hint union types aligned with backend literal schema values.
- Add focused tests for parser/utility behavior when the logic is not trivial.
