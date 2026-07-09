# Durable Memory Sweep Reviews

## Purpose

Memory Sweep should behave like a saved review draft. A sweep result is generated
once for a given ledger/wiki state, stored by the backend, and restored when the
teacher leaves and returns. It should not rerun just because the page remounted.

## User-Facing Behavior

- Open Memory Sweep:
  - If a saved review exists for the current ledger/wiki state, resume it.
  - If no saved review exists, generate once and save the result.
  - If a previous saved review exists but the ledger/wiki changed, show it as
    stale or refresh it automatically when the teacher has not edited it.
- Leave during generation:
  - Returning shows `Generating...` or the completed saved review.
- Leave after generation:
  - Returning shows the same cards, edited wording, and selected decisions.
- Discard:
  - Marks the saved review discarded and returns to a clean state.
- Refresh:
  - Generates a new saved review from the current ledger/wiki state.
- Apply:
  - Uses backend-stored decisions and blocks stale writes if the ledger/wiki
    changed after generation.
- Class home:
  - The Memory Sweep button shows a small status badge, for example
    `Draft saved Jul 9`, `Generating...`, `Stale draft`, or `Ready to review`.

## Architecture

Implement a concrete backend service:

`backend/app/services/memory_sweep_reviews.py`

Store reviews in SQLite:

`wiki.root / "workflow" / "memory_sweep_reviews.sqlite"`

This is deliberately not `WorkflowDraft`. Memory Sweep has no chat transcript
and no markdown artifact; it has generated cards, teacher edits, and structured
decisions.

The service can later be generalized if another structured review workflow needs
the same pattern, but the first implementation should stay specific and small.

## Stored Data

Use one `memory_sweep_review` table:

- `review_id`
- `workspace_id`
- `class_id`
- `status`
- `source_fingerprint`
- `source_json`
- `proposals_json`
- `decisions_json`
- `has_teacher_edits`
- `generated_at`
- `updated_at`
- `completed_at`
- `error`

Statuses:

- `generating`
- `ready`
- `stale`
- `applying`
- `completed`
- `discarded`
- `failed`

## Fingerprint

Each review stores a source fingerprint from the current Memory Sweep inputs:

- class id and subject
- sweep-eligible ledger row ids
- ledger row status, updated time, target, section, cluster key, and content hash
- relevant synthetic student-summary source markers
- hashes of relevant wiki target excerpts used by the sweep

If the fingerprint matches, resume. If it differs, the saved review is stale.

## Backend API

Add:

- `POST /api/classes/{class_id}/memory/sweep/review`
  - Open or create the saved review.
  - Optional body `{ "refresh": true }` forces a fresh review.
- `GET /api/classes/{class_id}/memory/sweep/review`
  - Return current saved review status for page bootstrap and class-home badge.
- `PATCH /api/classes/{class_id}/memory/sweep/review/{review_id}`
  - Persist edited wording and selected decisions.
- `POST /api/classes/{class_id}/memory/sweep/review/{review_id}/apply`
  - Apply backend-stored decisions after fingerprint validation.
- `POST /api/classes/{class_id}/memory/sweep/review/{review_id}/discard`
  - Mark the review discarded.

Keep existing `/memory/sweep/propose` and `/memory/sweep/apply` for tests and
temporary compatibility, but move the frontend to the review endpoints.

## Stale Handling

When opening a saved review whose fingerprint no longer matches:

- If `has_teacher_edits = false`, auto-refresh by default.
- If `has_teacher_edits = true`, return `status = stale` and keep the saved
  teacher work visible with actions:
  - `Refresh sweep`
  - `Keep reviewing`
  - `Discard`

Apply always validates the current fingerprint. If stale, return
`409 stale_review`.

## Frontend

Memory Sweep remains a normal review page, not an assistant-ui chat.

- Stop calling one propose request per queue.
- Open the saved review on mount.
- Poll only while status is `generating`.
- Persist decisions and edits to the backend.
- Use the saved review response to restore state after navigation.
- Show stale state with explicit actions.
- Show class-home Memory Sweep button badge from the backend status response.

## Tests

Backend:

- Opening twice with unchanged ledger/wiki returns the same review and does not
  call the consolidator twice.
- Different ledger/wiki fingerprint marks the old review stale or refreshes it.
- Decisions and edited wording survive a new service instance.
- Apply succeeds only when the fingerprint still matches.
- Apply returns `409 stale_review` when state changed.
- Discard prevents the old review from being resumed.

Frontend:

- Page mount calls one review endpoint, not five queue endpoints.
- Saved cards and decisions restore after remount.
- Stale review displays refresh/discard actions.
- Class-home Memory Sweep badge reflects backend status and date.
