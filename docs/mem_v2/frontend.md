# Memory V2 Frontend Map

This is the frontend-oriented map for Memory V2. The frontend remains a review
surface; it does not decide what is durable memory.

## Core Files

- `frontend/src/lib/api.ts` - typed API client models for Memory Sweep proposal
  cards, batch decisions, and apply responses.
- `frontend/src/app/classes/[classId]/memory-sweep/page.tsx` - teacher-facing
  sweep inbox. It displays proposed cards, collects local decisions, then
  submits one batch apply request.
- `frontend/src/app/classes/[classId]/memory/page.tsx` - Update Memory artifact
  session with typed start hints and backend-owned target confirmation state.
- `frontend/src/components/klassenpilot/proposed-memory-updates.tsx` - reusable
  proposed-memory update display in class memory review surfaces.
- `frontend/src/lib/markdown-diff.ts` - review diff helpers used by memory
  apply/proposal flows.

## UI Contract

- Memory Sweep is one public teacher-facing workflow, even though the backend
  internally packets candidates by target/scope.
- Cards are keyed by `card_id`, not only by `candidate_id`.
- Cards show an operation badge: `add`, `adjust`, `already_covered`,
  `reject_low_signal`, or `needs_decision`.
- `adjust` cards display the exact existing bullet from `replaces_content`
  beside the editable proposed replacement. The backend, not the UI, enforces
  exact replacement.
- A card may represent multiple `candidate_ids`; the UI should show
  `signal_count` and evidence summaries so repeated behavior is visible.
- Teacher choices are local pending decisions until submitted together.
- After submit, the backend writes approved curated memory first and updates
  represented ledger rows only after successful writes.
- `already_covered` and `reject` are review decisions, not wiki writes.

## Frontend Guardrails

- Do not apply cards one by one from the Memory Sweep inbox; use the batch apply
  endpoint for sweep decisions.
- Do not hide cards only because another card shares evidence. Overlapping
  evidence is resolved by the backend after the full decision set.
- Keep network type changes aligned with `backend/app/schemas/api.py`.
- Keep durable-memory target rules backend-owned. The UI can display targets and
  warnings, but it should not reimplement target allowlists.
