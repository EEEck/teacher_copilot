# Background Turn And Timeline Drafts Design

## Scope

Apply shared background-turn feedback to Lesson Plan and Update Memory chats.
Show active Update Memory drafts in the lesson timeline. Memory Sweep remains
out of scope pending separate workflow discussion.

## Design

- Reuse durable `turn_in_progress` from `WorkflowDraft`.
- Extend the shared assistant-ui `Thread` with a backend background-turn flag.
  Show one inline spinner row when either assistant-ui is locally running or the
  backend reports a resumed turn still running.
- Add `WorkflowDraftStore.list_active_ingest_drafts(class_id)` and overlay those
  drafts onto timeline entries through an optional `memory_draft_id`.
- Derive timeline actions centrally:
  - planned with no draft: `Add results`
  - matching active draft: `Edit memory draft`
  - taught with no active draft: `Correct with agent`
- Keep the existing timeline link parameters so opening an active draft resumes
  through the current backend identity rules.

## Verification

- Backend tests cover active draft lookup and timeline response overlay.
- Frontend tests cover all three action labels.
- Existing plan/update chat tests and the full deterministic suite pass.
