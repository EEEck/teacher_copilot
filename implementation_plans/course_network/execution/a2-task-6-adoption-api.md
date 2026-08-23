# A2 Task 6 — Structured Draft Helpers and Reviewed Adoption API

> Promoted from `.superpowers/sdd/2026-08-18-course-network-foundation/task-6-brief.md` on 2026-08-22. Completed; retained as the task-level contract.

## Goal

Deliver the teacher-HITL backend flow: open the matching course-network seed as
a structured draft, validate and review the exact artifact, and write the
canonical network only after the teacher confirms that same revision and hash.

## API and service contract

Routes:

- `GET /api/classes/{class_id}/course/network`
- `POST /api/classes/{class_id}/course/network/drafts`
- `GET /api/classes/{class_id}/course/network/drafts/{draft_id}`
- `POST /api/classes/{class_id}/course/network/drafts/{draft_id}/review`
- `POST /api/classes/{class_id}/course/network/drafts/{draft_id}/adopt`

`CourseNetworkService` owns `open_seed_draft`, `get_network`, `get_draft`,
async `review_seed`, and exact-snapshot `adopt_seed`.

## Exact-draft and review rules

- Reuse the existing `WorkflowDraftStore`, artifact revision/hash, and review
  snapshot lifecycle. Structured artifacts use canonical sorted JSON; no second
  draft database exists.
- Deterministic validation covers IDs, endpoints, relationship vocabulary,
  route match, acyclic `builds_on`, and curriculum provenance.
- A bounded no-tools reviewer evaluates chemistry/curriculum plausibility,
  misleading learning goals, unsupported claims, and unsafe content. It returns
  typed findings but never rewrites the seed.
- Provenance errors prevent LLM review; `revise`/`block` decisions prevent
  adoption; any artifact change invalidates a completed review.

## Adoption semantics

Opening returns 409 when the class already has a network. Opening or review
never writes canonical graph files. Adoption verifies the active exact review
snapshot, binds the class ID and route, converts nodes to `adopted`, writes
revision 1 through atomic storage, appends a `course_network_adopt` log entry,
rebuilds the index, and commits the draft. Stale adoption returns 409.

The router is a focused APIRouter under `/api`; the dependency cache is scoped
per wiki root. OpenAPI and agent/memory/wiki contracts must describe the
teacher-approved boundary.

## Completion record

The completed task added TDD coverage for canonical structured artifacts,
stale review/adoption, reviewer gates, recovery and concurrency. Final A2
review hardened durable recovery, envelope parity, idempotent opening, and
stale temporary cleanup. Fresh-sandbox API acceptance passed.
