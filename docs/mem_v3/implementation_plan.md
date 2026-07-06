# Memory V3 Implementation Plan

Test-driven, phased; each phase lands green before the next starts. Offline
pytest is the default; live DeepEval traces are opt-in (see `testing.md`).

## Phase 1 — Eval fixtures and goldens (before any behavior change)

Extract recorded beta data into offline fixtures so every later phase has a
regression target:

- `backend/tests/fixtures/mem_v3/organic_chemistry_ledger.json` — the real
  12-row / 4-claim over-capture case (from
  `beta_data/workspaces/w_demo_chem9b/.../memory_candidates.sqlite`),
  anonymized to candidate dicts.
- `backend/tests/fixtures/mem_v3/mbb_repetition_ledger.json` — the
  6×-applied MBB preference case.
- Golden assertions (initially `xfail`, flipped per phase):
  - folding: 12 rows in → ≤5 open clusters;
  - gate: singleton inferred claims held; ≥2-occasion clusters eligible;
    backend-verified fast_lane eligible; rejected-cluster suppressed unless a
    later verified fast_lane row appears;
  - sweep: ≤1 card per claim; class_state transition = UPDATE; zero raw
    warnings in the API payload.

Touchpoints: `backend/tests/test_mem_v3_ledger.py`,
`backend/tests/test_mem_v3_gate.py`, `backend/tests/test_mem_v3_sweep.py`,
fixture extraction script `backend/scripts/export_ledger_fixture.py`.

## Phase 2 — Deterministic ledger layer

`backend/app/services/memory_candidate_ledger.py` (+ small helpers):

1. Section vocabulary per target (define next to canonical targets in
   `backend/app/teacher_agent/memory_targets.py`); normalize on insert.
2. Insert-time folding: exact normalized dup → reject (keep row as
   `duplicate` for audit); content-word Jaccard ≥ 0.6 against open rows of
   the same target → adopt the matched row's `cluster_key` (cluster size
   remains audit data; promotion/display use distinct occasions).
3. History awareness on insert + listing: cluster matching an `applied` row →
   auto `already_covered`; cluster matching a `rejected` row → `suppressed`
   unless the new row has backend-verified `fast_lane=True`.
4. Promotion gate (pure function, unit-tested): eligibility per cluster —
   backend-verified fast_lane → eligible; inferred → distinct occasions ≥ 2
   (lesson/artifact anchors, else 6-hour buckets), recency-weighted score
   with OpenClaw starting weights; below gate → stays `captured`.
5. Silent decay: `expire_stale_candidates(now)` marks unreinforced singletons
   older than ~42 days `expired`; called on sweep propose (no cron needed).

Statuses are free text — no migration. New statuses: `duplicate`,
`suppressed`, `expired`.

## Phase 3 — Capture discipline

`backend/app/teacher_agent/memory_capture.py`, `prompts.py`,
`prompt_assembly.py`:

1. Add `speech_act` to capture and make `fast_lane` backend-owned:
   conduct requests can fast-lane teacher/copilot profiles, explicit
   store/update/remove requests can fast-lane content targets, compiled
   class-state/session targets never can. A real direct teacher quote is
   required; fabricated quotes downgrade to inferred/low.
2. Capture prompt rules (mem0 + hermes): candidates only from teacher
   messages; "most turns save nothing — silence is normal"; SAVE/SKIP
   examples including the one-off-formatting negative case.
3. Capture context block: current memory excerpts (already available via
   wiki context builders) + open ledger claim texts for the session's
   targets (small; ledger query at session start, cached on runtime).
   **Deferred to Phase 4** — insert-time folding already neutralizes
   re-captures deterministically, so this block is noise reduction, and
   Phase 4 builds the ledger-excerpt plumbing it needs anyway.
4. Keep typed-state repair, but route repaired candidates through the same
   tightened classification (repair must not re-create the explicit/high
   default).

## Phase 4 — Single-call sweep + structural validation

`backend/app/services/memory_sweep.py`, `backend/app/teacher_agent/agents.py`
(new agent method), `prompts.py`:

1. Build one consolidation input per sweep run: enumerate current bullets of
   in-scope memory files with ephemeral IDs (`M1..Mn` per file, assigned at
   call time); gate-passing claims with signal counts, occasion counts,
   dates; applied + rejected texts per target; today's date.
2. New agent call `consolidate_memory_sweep(...)` on the sweep-specific
   model (new setting `OPENAI_SWEEP_MODEL`, default = chat model; reasoning
   effort high). Output schema: list of operations
   `{claim_ids[], operation: add|update|delete|none, memory_id?, new_text?,
   target, section, rationale}` — mem0 contract, IDs from input only.
3. Structural validation (restores 2sweep §7): full claim coverage, IDs
   exist, UPDATE quotes the referenced bullet, allowlisted targets; one
   retry with the error; on second failure emit ONE plain-language notice
   object, log raw reason.
4. Map operations → existing `MemorySweepCandidate` card shape so
   `/memory/sweep/apply` and the current UI keep working before M1b lands:
   ADD → operation add; UPDATE → adjust (replaces_content = referenced
   bullet); DELETE → adjust-to-empty/compaction card; verified fast-lane
   clusters → pinned queue "Explicitly requested".
5. Delete: packet-by-section machinery, lexical validators, per-candidate
   unresolved fallback, two-pass alignment calls. Migrate the MBB/executive
   trace to the new call.

## Phase 5 — Budgets at apply

`backend/app/services/memory_apply.py` + a small `MemoryBudget` helper
(adapted from hermes `MemoryStore`, MIT):

1. Char budgets: teacher_profile / copilot_profile / class compact pages
   (~2,200 chars each, config constants).
2. Over-budget apply fails deterministically with "replace or remove
   entries first"; the sweep propose includes current usage per file so the
   model proposes compaction when near budget.

## Phase 6 — M1b sweep brief (frontend, separate PR)

As designed in the roadmap: `lib/sweep-brief.ts` + `MemorySweepBrief`
grouped Explicit-first / New / Changed (old → new) / Removed-compacted, three
uniform icon actions (Add / Not needed / Later), sticky submit bar, detail
cards preserved, StrictMode double-propose fix. Consumes the Phase-4 card
model unchanged.

## Order and PR boundaries

Phase 1+2 → PR "mem_v3 ledger + gate". Phase 3 → PR "mem_v3 capture".
Phase 4+5 → PR "mem_v3 single-call sweep + budgets". Phase 6 → PR "sweep
brief". Update `docs/claude_todo.md` status table as each lands.
