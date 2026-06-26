# Memory V2 Backend Map

This is the backend-oriented map for Memory V2. It points at the implementation
files and the boundaries that should stay stable while the sweep consolidator
evolves.

## Core Files

- `backend/app/teacher_agent/memory_capture.py` - shared candidate capture
  layer: validation, dedupe, caps, render helpers, typed-state repair, and
  runtime-to-ledger conversion support.
- `backend/app/teacher_agent/planning_state.py` - `PlanRuntime`; planning
  phase, plan state, evidence briefs, raw refs, plan version, and shared memory
  candidates.
- `backend/app/teacher_agent/memory_update_state.py` - `MemoryRuntime`; target
  resolution, lesson-result state, diary state, evidence briefs, raw refs, and
  shared memory candidates.
- `backend/app/teacher_agent/models.py` - structured output contracts:
  `PlanTurnOutput`, `IngestTurnOutput`, Memory Sweep alignment models, and
  Memory Sweep proposal/card models.
- `backend/app/teacher_agent/prompts.py` - durable candidate routing rules and
  separate Memory Sweep alignment/card prompts.
- `backend/app/services/memory_candidate_ledger.py` - SQLite raw evidence
  ledger and status transitions.
- `backend/app/services/memory_sweep.py` - packet building, alignment/card
  validation, unresolved fallback cards, target excerpts, and review card
  assembly.
- `backend/app/services/memory_apply.py` - deterministic teacher-approved wiki
  apply path.
- `backend/app/api/routes.py` - public API endpoints for proposal/apply and
  candidate review status compatibility.
- `backend/app/schemas/api.py` - API request/response models used by frontend
  and trace scripts.

## Lifecycle

1. Planning or Update Memory chat produces structured output.
2. Workflow runtime applies state patches and delegates memory-candidate merge
   and repair to the shared capture layer.
3. Completed turns persist validated candidates to the SQLite ledger.
4. Memory Sweep reads open ledger rows and builds hard-scope packets by target.
5. The isolated alignment pass groups every packet candidate exactly once into
   durable claim groups and compares those groups with current memory.
6. The card pass turns only validated alignment groups into review cards.
7. The sanitizer/validators enforce backend invariants: known candidate IDs,
   complete coverage, supported targets, review-only targets, group/card
   consistency, and evidence preservation.
8. `/memory/sweep/apply` processes all selected teacher decisions together:
   approved wiki writes first, ledger status updates second.

## Sweep Operations

Memory Sweep cards describe one claim-level operation against current curated
memory:

- `add` - append one new bounded memory bullet.
- `adjust` - replace one exact existing bullet in the same target/section with
  a broader or more accurate bullet. The card must include `replaces_content`
  copied exactly from the current memory excerpt; if the bullet is missing, the
  backend skips the write and leaves the represented ledger rows open.
- `already_covered` - no wiki write; mark represented rows applied-equivalent
  after the full decision set succeeds.
- `reject_low_signal` - no wiki write; teacher can reject or snooze the rows.
- `needs_decision` - no wiki write; teacher must decide how to interpret
  ambiguous or conflicting evidence.

`status_recommendation` remains as a compatibility field. `add` and `adjust`
map to `promote`; the other operations map directly.

## Backend Guardrails

- Chat routes must not write curated wiki memory.
- Proposal generation must not update ledger statuses.
- Raw ledger text is evidence, not canonical memory.
- Raw ledger evidence plus current curated memory should produce an observation
  or adjustment proposal. Durable memory stores the underlying preference, not
  the user's latest wording.
- Unsupported targets become warnings, not writes.
- Review-only targets such as `canonical_wiki` cannot be applied directly.
- One candidate row may support multiple review cards when the target scopes
  differ, but each card writes to exactly one target.

## Prompt Contract

The Memory Sweep prompts state that ledger rows are raw evidence for durable
claims, not one card per row. The alignment pass must make semantic grouping
inspectable with `surface_labels`, `shared_attributes`,
`distinguishing_attributes`, and `merge_test`. Those fields are not backend
synonym rules; they are model-produced evidence of why rows can or cannot become
one durable claim.

Prompt examples should teach the general operation, not memorize one regression.
Current examples use teacher/classroom cases: redox misconceptions expressed
through different labels, board-ready/copyable artifact wording, concrete
examples before formal rules, scoped lesson exceptions, and true sequencing
conflicts. The active system prompts must not contain MBB/McKinsey/executive
communication examples or hardcoded aliases. The card pass consumes the
validated alignment fields and writes one generalized durable memory sentence
from the shared attributes.

Card generation then maps alignment decisions to `add`, `adjust`,
`already_covered`, `needs_decision`, or `reject_low_signal`.

## Regression Trace

`scripts/trace_memory_mbb_executive_consolidation.py` remains the live check for
the original semantic-merge failure, but it is intentionally outside the
production prompt. The desired behavior is a single polished
`teacher_profile.md / Communication` card. With no current memory it should be
`add`; with narrow MBB memory plus executive evidence it should be `adjust`;
with generalized executive/MBB memory it should be `already_covered`.
