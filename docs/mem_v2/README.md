# Memory V2 Docs

This folder contains the working design and implementation notes for the
Memory V2 effort. The durable product contract still lives in
`../agent_contracts.md`; this folder is for the memory-specific architecture,
backend/frontend integration map, tests, traces, and known bugs.

## Read Order

1. `design.md` - full architecture/literature note and progress log.
2. `backend.md` - backend implementation map, route/service boundaries, and
   current lifecycle.
3. `frontend.md` - frontend Memory Sweep and memory-update UI/API map.
4. `testing.md` - deterministic tests, trace scripts, and live-model drift
   checks.
5. `candidate_capture_bug.md` - original MBB preference capture bug report and
   repro evidence.

## Current Shape

- Chat workflows capture review-only `memory_candidates`; they do not write
  durable wiki memory directly.
- `memory_capture.py` owns shared candidate validation/repair/merge behavior
  used by planning and Update Memory runtimes.
- `memory_candidate_ledger.py` stores raw cross-session evidence rows in
  SQLite.
- Memory Sweep uses a two-pass slow path: validated alignment groups normalize
  raw ledger rows into underlying durable claims, then review cards are
  generated only from those groups. Cards use `add`, `adjust`,
  `already_covered`, `reject_low_signal`, or `needs_decision`.
- `/memory/sweep/apply` applies teacher decisions as one decision set: wiki
  writes first, ledger status updates after successful writes.
- `teacher_profile.md`, `copilot_profile.md`, class compact memory files, and
  subject guides remain curated memory, not automatic projections of raw ledger
  rows.

## Core Backend Memory-Merge Check

When changing Memory Sweep contracts, prompts, backend grouping/apply logic, or
target names, run the focused deterministic tests and the live MBB/executive
merge trace:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_memory_targets.py tests\test_memory_sweep_backend.py tests\test_prompts.py -q
cd ..
.\backend\.venv\Scripts\python .\scripts\trace_memory_mbb_executive_consolidation.py --run-name manual-mbb-executive-merge
```

The trace should report `passed=true`, `full_merge_cards=1`, and one
`teacher_profile.md / Communication` review card representing all three seeded
candidate IDs. Keep this scenario as a regression trace, not as a hardcoded
system-prompt example or backend synonym rule.

## Non-Goals

- Do not add embeddings, graph memory, autonomous wiki writes, or broad agent
  orchestration just to improve Memory V2.
- Do not collapse `PlanRuntime` and `MemoryRuntime` into a broad base runtime.
  Keep workflow state separate and share only memory-candidate mechanics.
- Do not treat the SQLite ledger as prompt-facing truth before teacher review.
