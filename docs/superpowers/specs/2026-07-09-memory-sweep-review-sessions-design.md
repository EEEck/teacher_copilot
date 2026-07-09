# Durable Memory Sweep Review Sessions

## Purpose

Memory Sweep should resume like a durable review workflow, not like a chat draft.
The teacher should be able to start a sweep, leave the page while generation is
running, return to the same generated review, edit wording and decisions, leave
again, and later apply or discard the same review. The backend must avoid
regenerating the sweep while the underlying ledger/wiki snapshot is unchanged.

This keeps the existing `WorkflowDraft` abstraction focused on chat and markdown
artifact workflows. Memory Sweep gets a review-session abstraction because its
state is structured proposals, teacher edits, and decisions.

## Current Problem

- The Memory Sweep page stores proposals, edited wording, and decisions in React
  state only.
- Navigation loses the review state.
- Page load loops through review queues and calls `/memory/sweep/propose` once
  per queue, even though the backend sweep design expects one consolidation call
  across all eligible claims.
- Repeated opens can repeat expensive generation and produce confusing telemetry.
- `/memory/sweep/apply` trusts a client-submitted decision batch without a
  durable backend review snapshot.

## Recommended Architecture

Add a backend-owned `workflow_review_session` store under the existing wiki
workflow directory:

`wiki.root / "workflow" / "workflow_reviews.sqlite"`

Use one generic table for future review workflows, with a typed Memory Sweep
service on top:

- `review_id`
- `workspace_id`
- `class_id`
- `review_type`
- `status`
- `source_fingerprint`
- `source_json`
- `proposals_json`
- `decisions_json`
- `error_json`
- `created_at`
- `updated_at`
- `completed_at`

Initial statuses:

- `generating`
- `reviewing`
- `applying`
- `completed`
- `failed`
- `discarded`

`review_type = "memory_sweep"` is the first concrete user. Future structured
review workflows can reuse the table but should still get typed services and
schemas, not untyped frontend JSON contracts.

## Source Fingerprint

Memory Sweep open/resume behavior is keyed by a deterministic source
fingerprint. The fingerprint should include:

- class id and subject
- sweep-eligible ledger row ids
- relevant ledger row status, updated time, target, section, cluster key, and
  candidate content hash
- synthetic student-summary source markers
- hashes of relevant current wiki target excerpts/bullets used by the sweep

If the fingerprint is unchanged, the backend resumes the existing active review.
It does not regenerate. If the fingerprint changes because ledger rows or
relevant wiki memory changed, opening Memory Sweep creates a new review.

## API Shape

Add open-or-resume endpoint:

`POST /api/classes/{class_id}/memory/sweep/reviews`

It returns:

- `review_id`
- `status`
- `source_fingerprint`
- `proposals`
- `decisions`
- `warnings`
- `error`

If no matching review exists, the backend creates a review and runs one
generation across all queues. The first implementation may run generation in the
request and return `reviewing` when complete, but the contract should support
`generating` so the frontend can resume after navigation.

Add status/read endpoint:

`GET /api/classes/{class_id}/memory/sweep/reviews/{review_id}`

Add decision persistence endpoint:

`PATCH /api/classes/{class_id}/memory/sweep/reviews/{review_id}`

This persists edited card wording and selected actions. The frontend should
patch on each decision/edit, with simple debouncing for text edits.

Add apply endpoint:

`POST /api/classes/{class_id}/memory/sweep/reviews/{review_id}/apply`

Apply uses backend-stored decisions and validates that the current source
fingerprint still matches the review. If the ledger/wiki source changed, return
`409 stale_review`.

Add discard endpoint:

`POST /api/classes/{class_id}/memory/sweep/reviews/{review_id}/discard`

Add explicit fresh-start request flag:

`POST /api/classes/{class_id}/memory/sweep/reviews?fresh=1`

Fresh start discards the active matching review and generates a new one even if
the source fingerprint is unchanged.

## Backend Flow

Open/resume:

1. Validate class.
2. Expire stale candidates using the existing ledger gate behavior.
3. Build source snapshot and fingerprint.
4. Look for a non-terminal Memory Sweep review with the same fingerprint.
5. Return it if found.
6. Otherwise create `generating`, call `propose_memory_sweep_review` once with
   no queue filter, store the grouped proposals, and mark `reviewing`.

Apply:

1. Load the review and require `status = reviewing`.
2. Recompute the source fingerprint.
3. If it differs, return `409 stale_review`.
4. Validate all candidate ids are still open or valid synthetic ids.
5. Apply writing decisions through the existing `apply_curated_sweep_decisions`.
6. Update ledger row statuses through the existing status resolver.
7. Mark the review `completed`.

Failures:

- Generation failures mark the review `failed` with a teacher-safe error.
- A failed review can be discarded or retried.
- If the server dies while status is `generating`, the next open may mark the
  abandoned review `failed` and create a fresh review for the same fingerprint.

## Frontend Flow

The Memory Sweep page should stop calling per-queue `memorySweepPropose`.

On mount:

1. Call open-or-resume.
2. If `generating`, show a persistent generation state and poll the read
   endpoint.
3. If `reviewing`, render the persisted review cards and any saved decisions.
4. If `failed`, show retry/discard actions.

Teacher edits:

- Store wording edits and selected actions through the PATCH endpoint.
- Local component state can mirror the backend for responsiveness, but the
  backend is authoritative.

Apply:

- Disable controls and show `applying`.
- Call review apply by `review_id`.
- On success, show completion and refresh class memory/timeline data.
- On `409 stale_review`, show that memory changed and offer to start a fresh
  sweep.

Discard:

- Call discard.
- Clear local state.
- Return to an empty/new sweep state without applying decisions.

## UI Reuse

Do not use `assistant-ui` for Memory Sweep. Reuse only shared app-level helpers:

- operation loading text
- completion notifications
- pending-operation notifier pattern
- shared button/alert/card components

The page should feel like an inbox/review surface, not a chat surface.

## Compatibility

Keep the old `/memory/sweep/propose` and `/memory/sweep/apply` endpoints during
the migration for backend tests and older callers, but make the frontend use the
review-session endpoints. Once the new tests and UI are stable, the queue-scoped
propose behavior can be deprecated or limited to debugging.

## Tests

Backend:

- Opening Memory Sweep twice with unchanged ledger/wiki returns the same
  `review_id` and does not call the consolidator twice.
- Opening after ledger content/status changes creates a new review.
- A new service instance can hydrate a review from SQLite.
- Decisions and edited wording persist after reload.
- Apply succeeds when the source fingerprint matches.
- Apply returns `409 stale_review` when a ledger row or relevant wiki target
  changed after review generation.
- Discard marks the session discarded and the next normal open creates or
  resumes according to the current fingerprint.
- Fresh start discards/replaces the matching active review even when the
  fingerprint is unchanged.

Frontend:

- Page open calls one review endpoint, not five queue endpoints.
- Generated review state survives navigation/remount.
- Edits and decisions restore after remount.
- Applying uses `review_id`.
- Stale-review response blocks apply and shows a refresh path.
- Discard clears the current review UI.

Manual acceptance:

- Start Memory Sweep, leave during generation, return: spinner or completed
  cards resume.
- Return to an unchanged sweep later: no regeneration occurs.
- Edit several cards, leave, return: edits and selected decisions remain.
- Apply updates wiki/ledger once and marks review completed.
- If memory changes after generation, stale apply is blocked.

## Product Decision

Default behavior should resume the existing review for the same unchanged
ledger/wiki fingerprint. Regeneration should happen only when the source changes
or when the teacher explicitly chooses "Start fresh sweep".
