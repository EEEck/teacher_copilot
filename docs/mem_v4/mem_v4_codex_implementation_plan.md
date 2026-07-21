# Memory V4 Codex Implementation Plan

Status: in execution — shared branch `codex/mem4`
Date: 2026-07-17

This checklist is the execution source of truth for the V4 hardening work.
Update it as each PR-sized milestone is completed and reviewed.

## Central design

```text
teacher message
    ↓
LLM extracts possible memory claims
    ↓
Admission: valid teacher-originated evidence?
    ↓
Priority: explicit enough for fast lane?
    ↓
ledger → Sweep: merge, downgrade, reject, or propose
    ↓
Apply: teacher approval
    ↓
curated Markdown memory
```

The existing V3 lifecycle stays in place. V4 hardens admission, priority,
provenance, batching, Sweep visibility, and local diagnostics. Full chat-history
storage, a separate classifier service, graph memory, and automatic Markdown
writes remain out of scope.

## Current state before execution

- [x] V4 problem analysis and design reviewed with the owner.
- [x] V4 design document written in `docs/mem_v4/mem_v4_codex.md`.
- [x] Existing capture goldens reviewed.
- [x] Deterministic golden-trace harness drafted.
- [x] Deterministic trace smoke run executed.
- [x] Raw reasoning capture added to local developer traces.
- [x] Shared memory-classification context contract documented for all three workflows.
- [x] Production Admission behavior changed.
- [x] Production Priority/batching behavior changed.
- [x] Memory Sweep singleton visibility changed.
- [ ] DeepEval layer added.

Known integration boundary: the three workflows already provide bounded
history, typed runtime state, compact memory, evidence briefs, and review
candidates through their own prompt builders. A shared production
`MemoryClassificationContext` assembler is still intentionally pending; the
current implementation does not store or replay the full chat transcript and
does not introduce a separate classifier service.

## PR 0 — Developer traces and golden baseline

### Implementation

- [x] Extract raw reasoning events from local development SSE responses.
- [x] Aggregate reasoning per turn into local trace artifacts.
- [x] Keep raw reasoning out of teacher-facing SSE.
- [x] Extend the V4 golden trace script to save raw reasoning files.
- [x] Keep Apply disabled in the diagnostic harness.
- [x] Add/adjust deterministic trace tests.

### Review checks

- [x] Run deterministic two-case golden trace.
- [x] Run all deterministic goldens.
- [ ] Run one live golden with full prompt/tool/reasoning trace.
- [x] Confirm deterministic diagnostics do not change curated Markdown.
- [x] Confirm teacher-visible stream still contains only sanitized reasoning status.

### PR 0 exit condition

Developer traces are sufficient to diagnose model emission, prompt context,
tool calls, raw reasoning, and stage decisions without changing memory behavior.

The live golden remains an environment check rather than an exit blocker for
the deterministic work: the local API was unavailable during the PR 0 smoke
run, so that checkbox stays open until a local stack is running.

## PR 1 — Typed semantic Admission

### Canonical values

```python
SpeechAct = conduct_request | store_request | observation | unknown
Scope = turn | lesson | block | class | global | unknown
Admission = ignore | stage | needs_review
```

### Implementation

- [x] Add typed speech-act and scope fields with safe `unknown` defaults.
- [x] Add `scope_label` for bounded blocks such as organic chemistry.
- [x] Add backend-owned origin kind, turn index, message hash, and quote fingerprint.
- [x] Require exact teacher-message quote for new teacher-originated evidence.
- [x] Remove marker words as fast-lane authorization.
- [x] Make unknown speech act/scope ineligible for fast lane.
- [x] Make turn-scoped items non-durable.
- [x] Classify quote/claim mismatch as `needs_review`.
- [x] Keep teacher approval as the only durable-write boundary.
- [ ] Build one explicit `MemoryClassificationContext` assembly helper across Plan, Update Memory, and Discuss.
- [x] Add `scope` to the `remember(...)` tool contract so tool captures use the same classification schema.

### Review checks

- [x] Direct request without “always” is accepted.
- [x] Observation containing “always” is not fast lane.
- [x] Missing/fabricated quote becomes `needs_review`.
- [x] Lesson and block scope do not become global scope.
- [x] Unsupported targets are rejected or downgraded.

## PR 2 — Priority, grouping, and ledger provenance

### Implementation

- [x] Collect one capture batch per teacher turn.
- [x] Group candidates by target, section, scope, and material claim.
- [x] Fold exact and near duplicates before ledger insertion.
- [x] Add configurable `memory_capture_batch_max_candidates = 8` as an operational overflow guard.
- [x] Prevent overflow candidates from fast lane.
- [x] Preserve overflow as one compact `needs_review` item rather than silently dropping it.
- [x] Add quote-aware folding and origin metadata to ledger rows.
- [x] Defer legacy rows without origin metadata; sandbox scope starts with newly captured V4 rows.

### Review checks

- [ ] Short messages cannot create 10–20 fast-lane rows.
- [x] Long legitimate multi-claim messages remain representable.
- [x] Same-message retries count once.
- [x] Separate lessons can still reinforce a claim.
- [x] New fast-lane rows always contain origin and quote metadata.

## PR 3 — Memory Sweep as the second critical judge

### Implementation

- [x] Keep occasion counting as priority/reinforcement metadata.
- [x] Stop hiding all singleton candidates from Sweep.
- [x] Send bounded singleton, reinforced, fast-lane, and useful `needs_review` candidates to Sweep.
- [x] Add Sweep actions: promote, merge, already_covered, downgrade, reject, needs_review.
- [x] Allow Sweep to overturn weak explicit-looking candidates.
- [x] Preserve current teacher approval and Apply behavior.

### Review checks

- [x] Singleton inferred candidates reach Sweep.
- [x] False fast-lane candidates can be downgraded.
- [x] Already-covered claims become no-op decisions.
- [x] Related claims produce one review card.
- [x] Sweep never writes Markdown directly.

## PR 4 — Optional DeepEval layer

- [ ] Consume existing golden-trace JSON rather than creating a second execution path.
- [ ] Score Admission precision.
- [ ] Score Priority/fast-lane precision.
- [ ] Score Sweep merge/downgrade/reject/propose quality.
- [ ] Score Apply safety.
- [ ] Keep DeepEval opt-in and out of deterministic CI.

## Verification commands

From repository root:

```powershell
& .\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_memory_v4_golden_trace.py -q
& .\backend\.venv\Scripts\python.exe scripts\run_memory_v4_golden_trace.py --scenario all
```

For live local diagnostics:

```powershell
& .\backend\.venv\Scripts\python.exe scripts\run_memory_v4_golden_trace.py `
  --mode live --scenario two --run-sweep
```

If the local environment lacks pytest, use the project/CI environment and run
the script’s `py_compile` plus deterministic smoke checks locally.

## PR review rhythm

Each PR stops for review after its exit condition. The review bundle must show:

- changed checklist items;
- deterministic test output;
- one representative trace bundle;
- raw reasoning where the PR affects diagnostics;
- Admission/Priority/Sweep/Apply outcomes;
- known failures or environment limitations.
